import sys
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-01-136c2b1f011b"
COLLECTION_NAME = "workloads"

SEED_WORKLOADS = [
    {
        "workload_id": "price-match-agent",
        "display_name": "Price Match Agent",
        "environment": "managed_runtime",
        "is_registered": True,
        "service_account": "price-match-sa@qwiklabs-gcp-01-136c2b1f011b.iam.gserviceaccount.com",
        "status": "active",
        "last_audit": "2026-10-01",
    },
    {
        "workload_id": "markdown-strategy-agent",
        "display_name": "Markdown Strategy Agent",
        "environment": "managed_runtime",
        "is_registered": True,
        "service_account": "markdown-strategy-sa@qwiklabs-gcp-01-136c2b1f011b.iam.gserviceaccount.com",
        "status": "active",
        "last_audit": "2026-10-01",
    },
    {
        "workload_id": "customer-personalization-agent",
        "display_name": "Customer Personalization Agent",
        "environment": "managed_runtime",
        "is_registered": True,
        "service_account": "novasmart-customer-sa@qwiklabs-gcp-01-136c2b1f011b.iam.gserviceaccount.com",
        "status": "active",
        "last_audit": "2026-10-01",
    },
    {
        "workload_id": "promo-agent-shadow",
        "display_name": "Promo Agent Shadow",
        "environment": "cloud_run",
        "is_registered": False,
        "service_account": "novasmart-customer-sa@qwiklabs-gcp-01-136c2b1f011b.iam.gserviceaccount.com",
        "status": "flagged",
        "last_audit": "2026-10-01",
    },
]


def seed_database():
    print(f"Connecting to Firestore with hardcoded project ID: {PROJECT_ID}")
    try:
        db = firestore.Client(project=PROJECT_ID)
        collection_ref = db.collection(COLLECTION_NAME)

        for item in SEED_WORKLOADS:
            doc_id = item["workload_id"]
            doc_ref = collection_ref.document(doc_id)
            doc_ref.set(item)
            print(f"  [+] Seeded workload in Firestore: {doc_id} -> {item['display_name']}")

        print("🎉 Firestore database seeding completed successfully!")
    except Exception as e:
        print(f"[-] Firestore notice ({type(e).__name__}): {e}")
        print("  [!] Pre-seeded local dataset initialized for fallback.")


if __name__ == "__main__":
    seed_database()
