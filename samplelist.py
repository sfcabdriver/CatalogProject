from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import GearList, Base, GearItem, User

engine = create_engine('sqlite:///gearlistwithusers.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()


# Create user to set up an example of gear list
User1 = User(name="Andre", email="andre.menshov@gmail.com",
             picture='https://lh4.googleusercontent.com/-JW_0bQTZtx0/AAAAAAAAAAI/AAAAAAAAJ2Q/jyb5znNmByo/photo.jpg')
session.add(User1)
session.commit()

# Gear list for Andre's JMT Attempt
gearList1 = GearList(user_id=1, name="John Muir Trail in 9 days")

session.add(gearList1)
session.commit()

gearItem1 = GearItem(user_id=1, name="ProBar", description="organic power bar",
                     price="3.00", category="Nutrition", gear_list=gearList1)

session.add(gearItem1)
session.commit()

gearItem2 = GearItem(user_id=1, name="Sawyer Mini", description="ultralight water filtration system",
                     price="24.95", category="Hydration", gear_list=gearList1)

session.add(gearItem2)
session.commit()

gearItem3 = GearItem(user_id=1, name="Poncho/Tarp", description="poncho, which can be used as a tarp in case of rain",
                     price="45.99", category="Shelter", gear_list=gearList1)

session.add(gearItem3)
session.commit()

gearItem4 = GearItem(user_id=1, name="PlatypusPlus Bottle", description="flexible bottle, compatible with Sawyer Mini",
                     price="15.25", category="Hydration", gear_list=gearList1)

session.add(gearItem4)
session.commit()

gearItem5 = GearItem(user_id=1, name="Sun Hat", description="lightweight hat, with built-in neck cover",
                     price="$14.99", category="Clothing", gear_list=gearList1)

session.add(gearItem5)
session.commit()

gearItem6 = GearItem(user_id=1, name="Montrail Shoes", description="trail running shoes",
                     price="89.95", category="Clothing", gear_list=gearList1)

session.add(gearItem6)
session.commit()

gearItem7 = GearItem(user_id=1, name="Gatorade Bottle",
                     description="spare bottle for mixing electrolyte pills", price="1.00", category="Hydration", gear_list=gearList1)

session.add(gearItem7)
session.commit()


print "added gear items!"