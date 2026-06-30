import { formatPercent } from "../../utils/format";

test("formatPercent renders one decimal", () => {
  expect(formatPercent(0.1234)).toBe("12.3%");
});
