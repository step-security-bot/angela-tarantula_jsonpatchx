"""
Demo 1: Support desk profile corrections using Standard JSON Patch.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import HTTPException, Path

from examples.fastapi.shared import (
    Customer,
    CustomerId,
    create_app,
    get_customer,
    save_customer,
)
from jsonpatchx import StandardRegistry
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pydantic import JsonPatchFor

STRICT_JSON_PATCH = True

CustomerPatch = JsonPatchFor[Customer, StandardRegistry]
customer_patch = JsonPatchRoute(
    CustomerPatch,
    examples={
        "confetti-fix": {
            "summary": "Fix email and opt into marketing",
            "value": [
                {"op": "replace", "path": "/email", "value": "morgan@example.com"},
                {"op": "replace", "path": "/marketing_opt_in", "value": True},
            ],
        },
        "vip-sprinkles": {
            "summary": "Add VIP tag and update status",
            "value": [
                {"op": "add", "path": "/tags/-", "value": "vip"},
                {"op": "replace", "path": "/status", "value": "priority"},
            ],
        },
        "address-glowup": {
            "summary": "Update phone and address",
            "value": [
                {"op": "replace", "path": "/phone", "value": "+1-555-0111"},
                {
                    "op": "replace",
                    "path": "/address",
                    "value": "456 Pine Rd, Seattle, WA",
                },
            ],
        },
    },
    strict_content_type=STRICT_JSON_PATCH,
)

app = create_app(
    title="Demo 1: Support desk corrections",
    description="Standard JSON Patch on customer profiles using `JsonPatchFor[Model, StandardRegistry]`.",
)


@app.get(
    "/customers/{customer_id}",
    response_model=Customer,
    tags=["customers"],
    summary="Get a customer",
    description="Fetch a customer by id.",
)
def get_customer_endpoint(
    customer_id: Annotated[
        CustomerId,
        Path(...),
    ],
) -> Customer:
    customer = get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return customer


@app.patch(
    "/customers/{customer_id}",
    response_model=Customer,
    tags=["customers"],
    summary="Patch a customer",
    description="Apply a JSON Patch document to a Customer profile.",
    **customer_patch.route_kwargs(),
)
def patch_customer(
    customer_id: Annotated[
        CustomerId,
        Path(...),
    ],
    patch: Annotated[CustomerPatch, customer_patch.Body()],
) -> Customer:
    customer = get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    updated = patch.apply(customer)
    save_customer(customer_id, updated)
    return updated
