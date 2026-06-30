import { Injectable } from "@nestjs/common";

export interface PaymentRecord {
  orderId: string;
  chargeId: string;
  amount: number;
}

@Injectable()
export class PaymentsRepo {
  private readonly records = new Map<string, PaymentRecord>();

  async save(record: PaymentRecord): Promise<void> {
    this.records.set(record.chargeId, record);
  }

  async findByOrder(orderId: string): Promise<PaymentRecord | undefined> {
    return [...this.records.values()].find((r) => r.orderId === orderId);
  }
}
