from __future__ import annotations

from app.utils import api_error


class Handler:
    def __init__(self, next_handler=None):
        self.next_handler = next_handler

    def handle(self, ctx: dict):
        self.check(ctx)
        if self.next_handler:
            self.next_handler.handle(ctx)

    def check(self, ctx: dict):
        raise NotImplementedError


class UserIdValidator(Handler):
    def check(self, ctx: dict):
        if not ctx.get("x_user_id"):
            api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")


class ItemsNotEmptyValidator(Handler):
    def check(self, ctx: dict):
        if not ctx.get("items"):
            api_error(422, "VALIDATION_ERROR", "Пустой список items.")


class ExistingSkuValidator(Handler):
    def __init__(self, repo_factory, next_handler=None):
        super().__init__(next_handler=next_handler)
        self.repo_factory = repo_factory

    def check(self, ctx: dict):
        items = ctx.get("items", [])
        skus = [item.sku for item in items]
        variants = self.repo_factory.products().get_variants_by_skus(skus)
        by_sku = {variant.sku for variant in variants}
        for sku in skus:
            if sku not in by_sku:
                api_error(404, "SKU_NOT_FOUND", "SKU не найден.", {"sku": sku})


class StatusPayloadValidator(Handler):
    def check(self, ctx: dict):
        if not ctx.get("target_status"):
            api_error(422, "VALIDATION_ERROR", "Не передан целевой статус.")


class CreateOrderValidationChainFactory:
    @staticmethod
    def build(repo_factory):
        return UserIdValidator(ItemsNotEmptyValidator(ExistingSkuValidator(repo_factory)))
