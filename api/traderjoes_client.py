import requests

GRAPHQL_URL = "https://www.traderjoes.com/api/graphql"

QUERY = """
query SearchProducts($pageSize: Int, $currentPage: Int, $storeCode: String, $published: String = "1") {
  products(
    filter: {store_code: {eq: $storeCode}, published: {eq: $published}}
    pageSize: $pageSize
    currentPage: $currentPage
  ) {
    items {
      sku
      item_title
      retail_price
      availability
      sales_size
      sales_uom_description
    }
    total_count
    page_info {
      total_pages
    }
  }
}
"""

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.traderjoes.com",
    "Referer": "https://www.traderjoes.com/home/products",
    "User-Agent": "Mozilla/5.0 (compatible; grocery-classification-app/1.0)",
}


def fetch_store_catalog(store_code: str, page_size: int = 100, max_pages: int = 30):
    """Pulls the full published catalog for one Trader Joe's store via their
    public storefront GraphQL API (the same endpoint traderjoes.com itself
    calls; no auth token required)."""
    items = []
    page = 1
    while page <= max_pages:
        resp = requests.post(
            GRAPHQL_URL,
            json={
                "operationName": "SearchProducts",
                "variables": {
                    "storeCode": store_code,
                    "published": "1",
                    "currentPage": page,
                    "pageSize": page_size,
                },
                "query": QUERY,
            },
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()["data"]["products"]
        batch = data["items"]
        items.extend(batch)

        total_pages = data.get("page_info", {}).get("total_pages", page)
        if page >= total_pages or not batch:
            break
        page += 1
    return items
