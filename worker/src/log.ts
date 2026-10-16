import { LOG_EVENTS } from "./contracts/log-event";
import type { LogEvent, LogEventName } from "./contracts/log-event";

export type LogFields = Partial<Pick<LogEvent, "level" | "request_id" | "video_id" | "attrs">>;

const FIELDS: readonly string[] = ["level", "request_id", "video_id", "attrs"];
const LEVELS: readonly string[] = ["debug", "info", "warn", "error"];

export function log(event: LogEventName, fields: LogFields = {}): void {
  if (!(LOG_EVENTS as readonly string[]).includes(event)) {
    throw new Error(`unknown log event: ${event}`);
  }
  for (const key of Object.keys(fields)) {
    if (!FIELDS.includes(key)) throw new Error(`unknown log field: ${key}`);
  }
  if (fields.level !== undefined && !LEVELS.includes(fields.level)) {
    throw new Error(`unknown log level: ${fields.level}`);
  }
  const line: LogEvent = {
    ts: new Date().toISOString(),
    level: "info",
    service: "worker",
    event,
    attrs: {},
    ...fields,
  };
  console.error(JSON.stringify(line));
}
