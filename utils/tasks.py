from datetime import datetime, timedelta

def check_expiry_and_alerts(db):
    print(f"[{datetime.now()}] Running background task: Expiry and Low Stock Checks")
    
    # 1. Check for near-expiry products (e.g., within 7 days)
    upcoming_expiry_date = datetime.now() + timedelta(days=7)
    expiring_batches = list(db.inventory.find({
        "status": "active",
        "expiry_date": {"$lte": upcoming_expiry_date}
    }))
    
    for batch in expiring_batches:
        # Check if alert already exists to avoid duplicates
        existing_alert = db.alerts.find_one({
            "type": "expiry",
            "batch_id": batch["batch_id"]
        })
        if not existing_alert:
            days_left = (batch["expiry_date"] - datetime.now()).days
            # Suggest discount dynamically
            discount = "10%" if days_left > 3 else "25%"
            
            db.alerts.insert_one({
                "type": "expiry",
                "batch_id": batch["batch_id"],
                "product_id": batch["product_id"],
                "message": f"Batch {batch['batch_id']} expires in {days_left} days. Suggestion: Apply {discount} discount.",
                "created_at": datetime.now(),
                "status": "unread"
            })
            
    # 2. Check for low stock
    products = db.products.find()
    for product in products:
        # aggregate total active stock for this product
        pipeline = [
            {"$match": {"product_id": product["_id"], "status": "active"}},
            {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
        ]
        result = list(db.inventory.aggregate(pipeline))
        total_stock = result[0]["total"] if result else 0
        
        if total_stock < product.get("min_stock", 0):
            existing_stock_alert = db.alerts.find_one({
                "type": "low_stock",
                "product_id": product["_id"],
                "status": "unread"
            })
            if not existing_stock_alert:
                db.alerts.insert_one({
                    "type": "low_stock",
                    "product_id": product["_id"],
                    "message": f"Low stock for {product['name']}. Current stock: {total_stock}. Minimum: {product.get('min_stock', 0)}.",
                    "created_at": datetime.now(),
                    "status": "unread"
                })

def init_scheduler(app, db):
    from apscheduler.schedulers.background import BackgroundScheduler
    import atexit
    
    scheduler = BackgroundScheduler()
    # Run once a day at midnight in real app, but for demo we run every 5 minutes
    scheduler.add_job(func=lambda: check_expiry_and_alerts(db), trigger="interval", minutes=5)
    scheduler.start()
    
    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())
