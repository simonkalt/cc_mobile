# Stripe Products API - Raw Product Data

This document describes the endpoint that returns raw Stripe product data with full structure, including `marketing_features` as objects.

## Endpoint

**GET** `/api/subscriptions/products`

### Description

Retrieves all active Stripe products with their complete structure, exactly as returned by Stripe's API. This includes the `marketing_features` field as an array of objects with `name` properties.

**Authentication:** Not required (public endpoint)

### Query Parameters

| Parameter       | Type    | Required | Default | Description                                                  |
| --------------- | ------- | -------- | ------- | ------------------------------------------------------------ |
| `force_refresh` | boolean | No       | `false` | If `true`, bypasses cache and fetches fresh data from Stripe |

### Request Example

```javascript
// Basic request
const response = await fetch(
  "http://localhost:8000/api/subscriptions/products"
);

// Force refresh (bypass cache)
const response = await fetch(
  "http://localhost:8000/api/subscriptions/products?force_refresh=true"
);
```

### Response Format

**Status Code:** `200 OK`

```typescript
interface StripeProductsResponse {
  object: "list";
  data: StripeProduct[];
  has_more: boolean;
  url: string;
}

interface MarketingFeature {
  name: string;
}

interface StripeProduct {
  id: string;
  object: "product";
  active: boolean;
  attributes: any[];
  created: number; // Unix timestamp
  default_price: string | null; // Price ID
  description: string | null;
  images: string[];
  livemode: boolean;
  marketing_features: MarketingFeature[] | null; // Array of objects with name property
  metadata: Record<string, string>;
  name: string;
  package_dimensions: any | null;
  shippable: boolean | null;
  statement_descriptor: string | null;
  tax_code: string | null;
  type: string; // e.g., "service"
  unit_label: string | null;
  updated: number; // Unix timestamp
  url: string | null;
}
```

### Response Example

```json
{
  "object": "list",
  "data": [
    {
      "id": "prod_TidXk8okTNi03j",
      "object": "product",
      "active": true,
      "attributes": [],
      "created": 1767375351,
      "default_price": "price_1SlCGSQvXIwo0A0oom46SqgO",
      "description": "Get two years of unlimited cover letter generation at a HUGE discount.",
      "images": ["https://files.stripe.com/links/..."],
      "livemode": false,
      "marketing_features": [
        {
          "name": "Unlimited cover letter generations"
        },
        {
          "name": "Access to ALL available AI Models"
        },
        {
          "name": "HUGE discount for this two year service subscription"
        }
      ],
      "metadata": {},
      "name": "2 Year Subscription",
      "package_dimensions": null,
      "shippable": null,
      "statement_descriptor": null,
      "tax_code": "txcd_10203000",
      "type": "service",
      "unit_label": null,
      "updated": 1767375352,
      "url": null
    },
    {
      "id": "prod_Tha6p4iaSmlbSt",
      "object": "product",
      "active": true,
      "attributes": [],
      "created": 1767131940,
      "default_price": "price_1SkAwSQvXIwo0A0o52l0K5KS",
      "description": "Get one month free with the Annual payment option!",
      "images": ["https://files.stripe.com/links/..."],
      "livemode": false,
      "marketing_features": [
        {
          "name": "Unlimited cover letter generations"
        },
        {
          "name": "Access to ALL available AI models"
        },
        {
          "name": "One month FREE"
        }
      ],
      "metadata": {},
      "name": "Annual",
      "package_dimensions": null,
      "shippable": null,
      "statement_descriptor": null,
      "tax_code": "txcd_10203000",
      "type": "service",
      "unit_label": null,
      "updated": 1767374990,
      "url": null
    },
    {
      "id": "prod_Tha3qOMYK2CXuD",
      "object": "product",
      "active": true,
      "attributes": [],
      "created": 1767131755,
      "default_price": "price_1SkAtTQvXIwo0A0ojXgSly5n",
      "description": "Monthly payment allows you to cancel any time resume any time you want.",
      "images": ["https://files.stripe.com/links/..."],
      "livemode": false,
      "marketing_features": [
        {
          "name": "Unlimited cover letter generations"
        },
        {
          "name": "Access to ALL available AI models"
        },
        {
          "name": "Cancel anytime"
        }
      ],
      "metadata": {},
      "name": "Monthly Tier",
      "package_dimensions": null,
      "shippable": null,
      "statement_descriptor": null,
      "tax_code": "txcd_10203000",
      "type": "service",
      "unit_label": null,
      "updated": 1767375115,
      "url": null
    }
  ],
  "has_more": false,
  "url": "/v1/products"
}
```

## Frontend Implementation

### TypeScript/React Example

```typescript
// types.ts
export interface MarketingFeature {
  name: string;
}

export interface StripeProduct {
  id: string;
  object: string;
  active: boolean;
  attributes: any[];
  created: number;
  default_price: string | null;
  description: string | null;
  images: string[];
  livemode: boolean;
  marketing_features: MarketingFeature[] | null;
  metadata: Record<string, string>;
  name: string;
  package_dimensions: any | null;
  shippable: boolean | null;
  statement_descriptor: string | null;
  tax_code: string | null;
  type: string;
  unit_label: string | null;
  updated: number;
  url: string | null;
}

export interface StripeProductsResponse {
  object: string;
  data: StripeProduct[];
  has_more: boolean;
  url: string;
}

// api.ts
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

export async function fetchStripeProducts(
  forceRefresh: boolean = false
): Promise<StripeProductsResponse> {
  const url = new URL(`${API_BASE_URL}/api/subscriptions/products`);
  if (forceRefresh) {
    url.searchParams.set("force_refresh", "true");
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error(`Failed to fetch Stripe products: ${response.statusText}`);
  }

  return response.json();
}

// Component example
import React, { useEffect, useState } from "react";
import { fetchStripeProducts, StripeProduct } from "./api";

export function ProductsList() {
  const [products, setProducts] = useState<StripeProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProducts() {
      try {
        setLoading(true);
        const data = await fetchStripeProducts();
        setProducts(data.data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load products"
        );
      } finally {
        setLoading(false);
      }
    }

    loadProducts();
  }, []);

  if (loading) return <div>Loading products...</div>;
  if (error) return <div>Error: {error}</div>;
  if (products.length === 0) return <div>No products available</div>;

  return (
    <div className="products-list">
      {products.map((product) => (
        <div key={product.id} className="product-card">
          <h3>{product.name}</h3>
          <p>{product.description}</p>

          {product.marketing_features &&
            product.marketing_features.length > 0 && (
              <ul className="features">
                {product.marketing_features.map((feature, index) => (
                  <li key={index}>{feature.name}</li>
                ))}
              </ul>
            )}

          {product.images && product.images.length > 0 && (
            <img src={product.images[0]} alt={product.name} />
          )}
        </div>
      ))}
    </div>
  );
}
```

## Using Marketing Features

The `marketing_features` field is an array of objects, each with a `name` property:

```typescript
// Access marketing features
product.marketing_features?.forEach((feature) => {
  console.log(feature.name); // "Unlimited cover letter generations"
});

// Display in UI
{
  product.marketing_features?.map((feature, index) => (
    <li key={index}>{feature.name}</li>
  ));
}
```

## Key Differences from `/api/subscriptions/plans`

| Feature                | `/api/subscriptions/products` | `/api/subscriptions/plans`                      |
| ---------------------- | ----------------------------- | ----------------------------------------------- |
| **Structure**          | Raw Stripe product format     | Transformed plan format                         |
| **Marketing Features** | Objects with `name` property  | Array of strings                                |
| **Price Information**  | Only `default_price` ID       | Full price details (amount, currency, interval) |
| **Filtering**          | All active products           | Only products with recurring prices             |
| **Use Case**           | Display product catalog       | Subscription selection                          |

## Error Handling

### HTTP Status Codes

| Status Code                 | Description  | Action                                |
| --------------------------- | ------------ | ------------------------------------- |
| `200 OK`                    | Success      | Use the returned products             |
| `500 Internal Server Error` | Server error | Show error message, retry after delay |

### Error Response Format

```json
{
  "detail": "Failed to fetch Stripe products: [error message]"
}
```

## Notes

- **Raw Stripe Format**: This endpoint returns products exactly as Stripe's API returns them
- **Marketing Features**: The `marketing_features` field contains objects with `name` properties, not just strings
- **Active Products Only**: Only active products are returned
- **No Price Details**: This endpoint does not include price amounts or intervals - use `/api/subscriptions/plans` for subscription pricing information
- **Images**: Product images are included in the `images` array
