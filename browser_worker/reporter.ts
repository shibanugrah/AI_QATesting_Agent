import type {Reporter, FullResult, TestCase, TestResult} from '@playwright/test/reporter';
import fs from 'node:fs';
import path from 'node:path';
import type {WorkerRequest, JourneyResult} from './protocol';
const request:WorkerRequest=JSON.parse(fs.readFileSync(process.env.QA_WORKER_REQUEST!,'utf8'));
export default class MachineReporter implements Reporter {
  results:JourneyResult[]=[];
  onTestEnd(test:TestCase, result:TestResult) {
    const profile=test.title.split(':').at(-1)!;
    const file=path.join(request.output_dir,`${profile}.json`);
    const data:JourneyResult=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{id:request.journey.id,profile,status:'ERROR',duration_ms:result.duration,assertions:0,console:[],network:[],accessibility:[],error:'WORKER_SETUP_OR_TIMEOUT_ERROR',screenshot:null,trace:null};
    if(result.status!=='passed' && data.status==='SUCCEEDED') {data.status='ERROR';data.error='PLAYWRIGHT_TEST_NOT_PASSED';}
    this.results.push(data);
  }
  onEnd(result:FullResult) {
    fs.writeFileSync(path.join(request.output_dir,'result.json'),JSON.stringify({schema_version:1,request_id:request.request_id,project_id:request.project_id,environment_id:request.environment_id,browser:'chromium',playwright_status:result.status,tests:this.results}));
  }
}
