from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type, TypeVar

from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db import models

ModelT = TypeVar("ModelT", bound=models.Model)


@dataclass(frozen=True)
class TenantUnsafeService:
    """Helper to perform explicit cross-tenant operations under strict validation."""

    model: Type[ModelT]

    def __post_init__(self) -> None:  # pragma: no cover - simple guard
        manager = getattr(self.model, "_unsafe_objects", None)
        if manager is None:
            raise ValueError(
                f"{self.model.__name__} no expone `_unsafe_objects`; revise configuración multi-tenant."
            )
        # Validate that the model declares an empresa FK; otherwise usage is incorrect.
        try:
            self.model._meta.get_field("empresa")
        except FieldDoesNotExist as exc:  # pragma: no cover - programming error
            raise ValueError(
                f"{self.model.__name__} no tiene un campo `empresa`; no puede usarse con TenantUnsafeService."
            ) from exc

    @property
    def manager(self) -> models.Manager[ModelT]:
        return getattr(self.model, "_unsafe_objects")

    def _build_valid_condition(self, empresa_id: int, allow_null_empresa: bool) -> models.Q:
        if empresa_id is None:
            raise ValueError("`empresa_id` es obligatorio para operaciones sin aislamiento automático.")
        field = self.model._meta.get_field("empresa")
        empresa_lookup = {field.attname: empresa_id}
        condition = models.Q(**empresa_lookup)
        if allow_null_empresa:
            condition |= models.Q(**{f"{field.name}__isnull": True})
        return condition

    def filter(
        self,
        *,
        empresa_id: int,
        allow_null_empresa: bool = False,
        **filters: Any,
    ) -> models.QuerySet[ModelT]:
        condition = self._build_valid_condition(empresa_id, allow_null_empresa)
        qs = self.manager.filter(**filters)
        invalid = qs.exclude(condition)
        if invalid.exists():
            raise PermissionDenied(
                "Se detectaron registros de otra empresa al usar acceso sin aislamiento automático."
            )
        return qs.filter(condition)

    def get(
        self,
        *,
        empresa_id: int,
        allow_null_empresa: bool = False,
        **filters: Any,
    ) -> ModelT:
        return self.filter(empresa_id=empresa_id, allow_null_empresa=allow_null_empresa, **filters).get()

    def update(
        self,
        *,
        empresa_id: int,
        allow_null_empresa: bool = False,
        filters: Optional[Dict[str, Any]] = None,
        updates: Optional[Dict[str, Any]] = None,
    ) -> int:
        filters = filters or {}
        updates = updates or {}
        qs = self.filter(empresa_id=empresa_id, allow_null_empresa=allow_null_empresa, **filters)
        return qs.update(**updates)


def tenant_unsafe_service(model: Type[ModelT]) -> TenantUnsafeService:
    """Factory helper to obtain the unsafe service for a given model."""

    return TenantUnsafeService(model)
