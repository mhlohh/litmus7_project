from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

#This url contains postgresql:passsword//localhost:protnumber/name of database
db_url = "postgresql://postgres:9887@localhost:5432/muhsilnr"
engine = create_engine(db_url) #engine takes input as url as top 
session = sessionmaker(autoflush=False,autocommit=False, bind =engine) #This is database intialization