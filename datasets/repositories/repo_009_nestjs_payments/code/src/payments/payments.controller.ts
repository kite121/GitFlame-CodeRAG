import { Body, Controller, Post } from "@nestjs/common";
import { PaymentsService } from "./payments.service";

@Controller("payments")
export class PaymentsController {
  constructor(private readonly payments: PaymentsService) {}

  @Post("charge")
  charge(@Body() body: { orderId: string; amount: number }) {
    return this.payments.charge(body.orderId, body.amount);
  }

  @Post("refund")
  refund(@Body() body: { chargeId: string }) {
    return this.payments.refund(body.chargeId);
  }
}
