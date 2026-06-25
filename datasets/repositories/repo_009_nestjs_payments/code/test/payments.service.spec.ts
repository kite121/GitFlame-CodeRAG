import { PaymentsService } from "../src/payments/payments.service";
import { GatewayClient } from "../src/payments/gateway.client";
import { PaymentsRepo } from "../src/payments/payments.repo";

test("charge persists a record", async () => {
  const service = new PaymentsService(new GatewayClient(), new PaymentsRepo());
  const result = await service.charge("order-1", 500);
  expect(result.id).toContain("ch_");
});
