import pytest
from app.services.ingestion_service import process_csv
from sqlalchemy.orm import Session
from app.models.schemas import Product
from app.models.database import SessionLocal, Base, engine

def test_custom_mapping():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    csv_bytes = b"sku,title,mystery_col,drop_me\n100,Test,Value1,Secret\n"
    mapping = {
        "sku": "sku",
        "title": "title",
        "My Custom Name": "mystery_col",
        "__ignore__1": "drop_me"
    }
    job, product_ids = process_csv(db, csv_bytes, "test.csv", mapping)
    p = db.query(Product).filter(Product.id == product_ids[0]).first()
    assert p.attributes["My Custom Name"] == "Value1"
    assert "drop_me" not in p.attributes
    print("Test passed!")
    db.close()

if __name__ == "__main__":
    test_custom_mapping()
