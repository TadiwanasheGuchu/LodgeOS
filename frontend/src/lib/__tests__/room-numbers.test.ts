import { describe, expect, it } from "vitest";
import { parseRoomNumbers } from "@/lib/room-numbers";

describe("parseRoomNumbers", () => {
  it("expands ranges and keeps single labels", () => {
    expect(parseRoomNumbers("101-103, 110, Tent 1").numbers).toEqual(["101", "102", "103", "110", "Tent 1"]);
  });
  it("supports prefixed ranges and zero padding", () => {
    expect(parseRoomNumbers("A1-A3").numbers).toEqual(["A1", "A2", "A3"]);
    expect(parseRoomNumbers("08-10").numbers).toEqual(["08", "09", "10"]);
  });
  it("rejects backwards ranges, duplicates and invalid labels", () => {
    expect(parseRoomNumbers("10-5").error).toMatch(/backwards/);
    expect(parseRoomNumbers("1-3, 2").error).toMatch(/more than once: 2/);
    expect(parseRoomNumbers("#!").error).toMatch(/not a valid/);
    expect(parseRoomNumbers("1-500").error).toMatch(/more than 200/);
  });
});
