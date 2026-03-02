"""Test data simulator for scraped loads"""
import random
from datetime import datetime, timedelta
from src.utils.logger import logger
from src.database.database import db
from src.database.models import Load, Broker


class TestDataSimulator:
    """Simulates scraped load data for testing"""
    
    # Sample cities for origin/destination
    CITIES = [
        "Los Angeles, CA", "New York, NY", "Chicago, IL", "Houston, TX",
        "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX", "San Diego, CA",
        "Dallas, TX", "San Jose, CA", "Austin, TX", "Jacksonville, FL",
        "Fort Worth, TX", "Columbus, OH", "Charlotte, NC", "San Francisco, CA",
        "Indianapolis, IN", "Seattle, WA", "Denver, CO", "Boston, MA"
    ]
    
    EQUIPMENT_TYPES = ["Dry Van", "Refrigerated", "Flatbed", "Step Deck", "Hotshot"]
    
    BROKER_NAMES = [
        "ABC Logistics", "XYZ Freight", "Global Transport", "Express Shipping",
        "Prime Movers", "Fast Track Logistics", "Reliable Carriers", "Swift Transport"
    ]
    
    BROKER_EMAILS = [
        "broker1@abclogistics.com", "dancartertrans@gmail.com", "info@globaltransport.com",
        "sales@expressshipping.com", "dispatch@primemovers.com", "contact@fasttrack.com",
        "info@reliablecarriers.com", "sales@swifttransport.com"
    ]
    
    COMMODITIES = [
        "General Freight", "Electronics", "Food Products", "Building Materials",
        "Automotive Parts", "Furniture", "Textiles", "Machinery"
    ]
    
    def _generate_load_id(self) -> str:
        """Generate a unique load ID"""
        return f"DAT{random.randint(100000, 999999)}"
    
    def _calculate_miles(self, origin: str, destination: str) -> int:
        """Calculate approximate miles (simplified)"""
        # Simple calculation based on city pairs
        base_miles = random.randint(200, 2500)
        return base_miles
    
    def _generate_rate(self, miles: int) -> float:
        """Generate rate based on miles"""
        # Rate per mile between $1.50 and $3.50
        rate_per_mile = random.uniform(1.5, 3.5)
        base_rate = miles * rate_per_mile
        # Add some variation
        rate = base_rate + random.uniform(-200, 500)
        return round(rate, 2)
    
    async def create_test_loads(self, count: int = 8) -> int:
        """Create test loads in the database"""
        logger.info(f"Creating {count} test loads...")
        
        created_count = 0
        
        try:
            with db.get_session() as session:
                for i in range(count):
                    # Generate random origin and destination
                    origin = random.choice(self.CITIES)
                    destination = random.choice([c for c in self.CITIES if c != origin])
                    
                    load_id = self._generate_load_id()
                    
                    # Check if load already exists
                    existing = session.query(Load).filter(Load.load_id == load_id).first()
                    if existing:
                        continue
                    
                    miles = self._calculate_miles(origin, destination)
                    rate = self._generate_rate(miles)
                    
                    # Generate dates
                    pickup_date = datetime.now() + timedelta(days=random.randint(1, 7))
                    delivery_date = pickup_date + timedelta(days=random.randint(1, 5))
                    
                    # Select broker
                    broker_idx = random.randint(0, len(self.BROKER_NAMES) - 1)
                    broker_name = self.BROKER_NAMES[broker_idx]
                    broker_email = self.BROKER_EMAILS[broker_idx]
                    
                    # Create or get broker
                    broker = session.query(Broker).filter(Broker.email == broker_email).first()
                    if not broker:
                        broker = Broker(
                            name=broker_name,
                            email=broker_email,
                            phone=f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}",
                            company=broker_name
                        )
                        session.add(broker)
                        session.flush()
                    
                    # Create load
                    load = Load(
                        load_id=load_id,
                        origin=origin,
                        destination=destination,
                        miles=miles,
                        rate=rate,
                        equipment_type=random.choice(self.EQUIPMENT_TYPES),
                        pickup_date=pickup_date,
                        delivery_date=delivery_date,
                        weight=random.randint(10000, 45000),
                        commodity=random.choice(self.COMMODITIES),
                        broker_name=broker_name,
                        broker_email=broker_email,
                        broker_phone=broker.phone,
                        dat_url=f"https://dat.com/loads/{load_id}",
                        status='new',
                        raw_data=f'{{"test": true, "load_id": "{load_id}"}}'
                    )
                    
                    session.add(load)
                    created_count += 1
                
                session.commit()
                logger.info(f"Successfully created {created_count} test loads")
                return created_count
        
        except Exception as e:
            logger.error(f"Error creating test loads: {e}")
            raise
