import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';
import type {WorkerRequest, JourneyResult} from './protocol';

const request:WorkerRequest = JSON.parse(fs.readFileSync(process.env.QA_WORKER_REQUEST!, 'utf8'));
const credentials:Record<string,string> = JSON.parse(process.env.QA_WORKER_CREDENTIALS || '{}');
if(request.schema_version !== 1 || !request.project_id || !request.request_id) throw new Error('WORKER_PROTOCOL_INVALID');
const clean = (value:string) => {
  for(const secret of Object.values(credentials)) if(secret) value=value.split(secret).join('[REDACTED]');
  return value.replace(/(https?:\/\/[^\s?]+)\?\S*/gi,'$1?[REDACTED]')
    .replace(/(bearer|basic)\s+\S+/gi,'$1 [REDACTED]')
    .replace(/((?:password|token|secret|cookie|authorization)\s*[:=]\s*)[^\n,;]+/gi,'$1[REDACTED]');
};

for(const profile of request.journey.profiles) {
  test(`${request.journey.id}:${profile.name}`, async ({context, page}, testInfo) => {
    const started=Date.now();
    const result:JourneyResult={id:request.journey.id,profile:profile.name,status:'SUCCEEDED',duration_ms:0,assertions:0,console:[],network:[],accessibility:[],error:null,screenshot:null,trace:null};
    let policyBlocked=false;
    let networkCount=0;
    let eventOverflow=false;
    await page.setViewportSize({width:profile.width,height:profile.height});
    await context.routeWebSocket('**/*', ws=>{policyBlocked=true;ws.close();});
    await context.route('**/*', async route => {
      if(++networkCount>1000) {policyBlocked=true;await route.abort();return;}
      const req=route.request();
      try {
        const answer=await fetch(request.broker_url, {method:'POST',headers:{'content-type':'application/json','authorization':request.broker_token},
          body:JSON.stringify({url:req.url(),method:req.method(),headers:await req.allHeaders(),body:req.postDataBuffer()?.toString('base64')||null}),
          signal:AbortSignal.timeout(request.timeout_ms)});
        const payload=await answer.json() as {status?:number;headers?:Record<string,string>;body?:string;error?:string};
        if(!answer.ok || payload.error) {
          policyBlocked = answer.status === 403 || policyBlocked;
          if(result.network.length<100) result.network.push({url:clean(req.url()),error:clean(payload.error||'BROKER_ERROR')});
          await route.abort();
        } else {
          const headers={...payload.headers};
          delete headers['content-encoding'];delete headers['transfer-encoding'];delete headers['content-length'];
          await route.fulfill({status:payload.status!,headers,body:Buffer.from(payload.body!,'base64')});
        }
      } catch {if(result.network.length<100) result.network.push({url:clean(req.url()),error:'BROKER_UNAVAILABLE'});await route.abort();}
    });
    page.on('console', event=>{if(result.console.length<100)result.console.push({type:event.type(),text:clean(event.text()).slice(0,2000)});else eventOverflow=true;});
    page.on('pageerror', error=>{if(result.console.length<100)result.console.push({type:'error',text:clean(error.message).slice(0,2000)});else eventOverflow=true;});
    page.on('requestfailed', req=>{if(result.network.length<100)result.network.push({url:clean(req.url()),error:clean(req.failure()?.errorText||'REQUEST_FAILED')});});
    await context.tracing.start({screenshots:false,snapshots:false,sources:false});
    try {
      for(const step of request.journey.steps) {
        const locator=step.selector ? page.locator(step.selector) : null;
        switch(step.action) {
          case 'goto':
            if(!/^https?:\/\//.test(step.value!)) throw new Error('NAVIGATION_SCHEME_BLOCKED');
            await page.goto(step.value!, {waitUntil:'load'});break;
          case 'fill': {
            const value=step.credential_ref ? credentials[step.credential_ref] : step.value;
            if(value===undefined || value===null) {policyBlocked=true;throw new Error('CREDENTIAL_UNAVAILABLE');}
            await locator!.fill(value);break;
          }
          case 'click': await locator!.click();break;
          case 'check': await locator!.check();break;
          case 'select': await locator!.selectOption(step.value!);break;
          case 'expect_text': await expect(locator!).toContainText(step.value!);result.assertions++;break;
          case 'expect_visible': await expect(locator!).toBeVisible();result.assertions++;break;
          case 'expect_url': await expect(page).toHaveURL(step.value!);result.assertions++;break;
        }
      }
      if(request.kind==='accessibility') {
        const scan=await new AxeBuilder({page}).analyze();
        result.accessibility=scan.violations.map(v=>({id:v.id,impact:v.impact||null,selectors:v.nodes.flatMap(n=>n.target.map(String)).slice(0,20)}));
        expect(result.accessibility, 'configured automated accessibility violations').toHaveLength(0);
        result.assertions++;
      }
      if(request.journey.fail_on_console_error) expect(result.console.filter(c=>c.type==='error'),'browser console errors').toHaveLength(0);
      if(request.journey.fail_on_network_error) expect(result.network,'browser network failures').toHaveLength(0);
      if(policyBlocked) throw new Error('BROWSER_TARGET_POLICY_BLOCKED');
      if(eventOverflow) throw new Error('BROWSER_EVENT_BUDGET_EXCEEDED');
      // Navigation alone does not certify a journey.
      if(request.kind==='browser_e2e' && result.assertions===0) throw new Error('NO_JOURNEY_ASSERTIONS');
    } catch(error) {
      result.status=policyBlocked?'BLOCKED':eventOverflow?'ERROR':'FAILED';
      result.error=clean(error instanceof Error?error.message:String(error)).slice(0,4000);
      throw error;
    } finally {
      try {
        // Remove known secret-bearing text before retaining pixels. All inputs are masked.
        await page.evaluate(values=>{
          const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
          while(walker.nextNode()) {
            const node=walker.currentNode;
            if(values.some(v=>v && node.textContent?.includes(v)) || /(?:token|password|secret|cookie|authorization)\s*[:=]/i.test(node.textContent||'')) node.textContent='[REDACTED]';
          }
        },Object.values(credentials));
        const screenshot=path.join(request.output_dir,`${profile.name}.png`);
        await page.screenshot({path:screenshot,mask:[page.locator('input,textarea,[data-qa-private]')],timeout:3000});
        result.screenshot=screenshot;
      } catch {result.error=(result.error||'')+' SCREENSHOT_UNAVAILABLE';}
      const trace=path.join(request.output_dir,`${profile.name}.zip`);
      try {await context.tracing.stop({path:trace});result.trace=trace;} catch {result.error=(result.error||'')+' TRACE_UNAVAILABLE';}
      result.duration_ms=Date.now()-started;
      fs.writeFileSync(path.join(request.output_dir,`${profile.name}.json`),JSON.stringify(result));
    }
  });
}
