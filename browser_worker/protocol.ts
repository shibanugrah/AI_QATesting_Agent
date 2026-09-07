export interface Step {
  action: 'goto'|'fill'|'click'|'check'|'select'|'expect_text'|'expect_visible'|'expect_url';
  selector: string|null;
  value: string|null;
  credential_ref: string|null;
}
export interface WorkerRequest {
  schema_version: 1;
  request_id: string;
  project_id: string;
  environment_id: 'local'|'staging';
  kind: 'browser_e2e'|'accessibility'|'web_diagnostics';
  journey: {id:string; steps:Step[]; profiles:{name:string;width:number;height:number}[]; fail_on_console_error:boolean; fail_on_network_error:boolean};
  timeout_ms: number;
  broker_url: string;
  broker_token: string;
  output_dir: string;
}
export interface JourneyResult {
  id: string;
  profile: string;
  status: 'SUCCEEDED'|'FAILED'|'ERROR'|'BLOCKED';
  duration_ms: number;
  assertions: number;
  console: {type:string;text:string}[];
  network: {url:string;error:string}[];
  accessibility: {id:string;impact:string|null;selectors:string[]}[];
  error: string|null;
  screenshot: string|null;
  trace: string|null;
}
