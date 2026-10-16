import { describe, expect, test, vi } from "vitest";
import { LOG_EVENTS } from "../src/contracts/log-event";
import type { LogEvent } from "../src/contracts/log-event";
import type { TranscriptResult } from "../src/contracts/transcript-result";
import { log } from "../src/log";

describe("generated types", () => {
  test("a valid transcript result and log line type-check", () => {
    const result: TranscriptResult = {
      video_id: "dQw4w9WgXcQ",
      status: "ok",
      lang: "en",
      source: "manual",
      word_count: 3,
      truncated: false,
      sponsor_ratio: 0.25,
      pages: ["one two three"],
    };
    const line: LogEvent = {
      ts: "2026-10-16T10:00:00.000Z",
      level: "info",
      service: "worker",
      event: "service.started",
      attrs: { version: "0.1.0" },
    };
    expect(result.status).toBe("ok");
    expect(line.event).toBe("service.started");
  });

  test("invalid shapes are compile errors", () => {
    // @ts-expect-error a bad status
    const badStatus: TranscriptResult["status"] = "done";
    // @ts-expect-error an unknown event
    const badEvent: LogEvent["event"] = "nope";
    expect([badStatus, badEvent]).toHaveLength(2);
  });

  test("the runtime catalogue lists every event", () => {
    expect([...LOG_EVENTS]).toEqual(["service.started", "fetch.transcript", "sponsorblock.call"]);
  });
});

describe("log", () => {
  test("writes one JSON line on standard error", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    log("sponsorblock.call", { video_id: "dQw4w9WgXcQ", attrs: { status: 200 } });
    expect(spy).toHaveBeenCalledTimes(1);
    const line = JSON.parse(String(spy.mock.calls[0]?.[0])) as LogEvent;
    spy.mockRestore();
    expect(line).toMatchObject({
      level: "info",
      service: "worker",
      event: "sponsorblock.call",
      video_id: "dQw4w9WgXcQ",
      attrs: { status: 200 },
    });
    expect(line.ts).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });

  test("throws on an event outside the catalogue", () => {
    // @ts-expect-error not in the catalogue
    expect(() => log("not.in.catalogue")).toThrow(/unknown log event/);
  });

  test("throws on an unknown field", () => {
    // @ts-expect-error not a log field
    expect(() => log("service.started", { bogus: 1 })).toThrow(/unknown log field/);
  });
});
