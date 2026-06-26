import { Injectable } from "@nestjs/common";

@Injectable()
export class GatewayClient {
  async charge(amount: number): Promise<{ id: string }> {
    if (amount <= 0) {
      throw new Error("invalid amount");
    }
    // Pretend to call an external PSP.
    return { id: `ch_${Math.floor(Math.random() * 1e6)}` };
  }

  async refund(chargeId: string): Promise<void> {
    void chargeId;
  }
}
