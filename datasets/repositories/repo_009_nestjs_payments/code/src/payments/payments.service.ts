import { Injectable } from "@nestjs/common";
import { GatewayClient } from "./gateway.client";
import { PaymentsRepo } from "./payments.repo";

@Injectable()
export class PaymentsService {
  constructor(
    private readonly gateway: GatewayClient,
    private readonly repo: PaymentsRepo,
  ) {}

  async charge(orderId: string, amount: number): Promise<{ id: string }> {
    // BUG: no idempotency key, so retries double-charge the customer.
    const result = await this.gateway.charge(amount);
    await this.repo.save({ orderId, chargeId: result.id, amount });
    return { id: result.id };
  }

  async refund(chargeId: string): Promise<void> {
    await this.gateway.refund(chargeId);
  }
}
