import { Module } from "@nestjs/common";
import { PaymentsController } from "./payments/payments.controller";
import { PaymentsService } from "./payments/payments.service";
import { GatewayClient } from "./payments/gateway.client";
import { PaymentsRepo } from "./payments/payments.repo";

@Module({
  controllers: [PaymentsController],
  providers: [PaymentsService, GatewayClient, PaymentsRepo],
})
export class AppModule {}
