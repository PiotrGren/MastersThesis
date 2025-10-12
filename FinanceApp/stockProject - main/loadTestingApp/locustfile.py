from locust import FastHttpUser ,HttpUser, task, constant, between, events
import random
import string
import faker
import psycopg2
from datetime import datetime
import os
from gevent.lock import Semaphore

timeBetweenRequests=float(os.getenv("TIME_BETWEEN_REQUESTS"))
activeWeigth = int(os.getenv("ACTIVE_USER_WEIGHT",2))
activeWithAnalizeWeigth = int(os.getenv("ACTIVE_USER_WITH_ANALIZE_WEIGHT",2))
allLocustsSpawned = Semaphore()
allLocustsSpawned.acquire()

@events.spawning_complete.add_listener
def onHatchComplete(**kw):
    allLocustsSpawned.release()


# Konfiguracja połączenia z bazą danych
conn = psycopg2.connect(
    dbname="test_stock",  # Nazwa bazy danych
    user="postgres",  # Użytkownik bazy danych
    password="postgres",  # Hasło do bazy danych
    host="db_test",  # Adres hosta (może być też 'db' jeśli baza działa w kontenerze Dockera)
    port="5432"  # Port, na którym działa PostgreSQL
)
cursor = conn.cursor()

# Inicjalizujemy generator danych
fake = faker.Faker()

def generateRandomData():
    username = fake.user_name()
    name = fake.first_name()
    surname = fake.last_name()
    email = fake.email()
    password = generateValidPassword()

    return {
        "username": username,
        "password": password,
        "name": name,
        "surname": surname,
        "email": email
    }

def generateValidPassword():
    password = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=12))
    return password

def register(self):
    login = generateRandomData()
    self.client.post("/api/signUp", json=login, context={"userClass": self.userClass})
    data = {
        'username': login['username'],
        'password': login['password']
    }
    response = self.client.post("/api/signIn",json=data, context={"userClass": self.userClass})
    self.token = response.json()['token']
    companyName = fake.company()
    self.client.post("/api/addCompany",headers={"authorization": "Token " + self.token}, json={"name":companyName}, context={"userClass": self.userClass})
    allLocustsSpawned.wait()    

def buyOffer(self, companyId, maxAmount):
    userInfoResponse = self.client.get("/api/user", headers={"authorization": "Token " + self.token}, context={"userClass": self.userClass})
    userInfo = userInfoResponse.json()
    if userInfo['moneyAfterTransations'] < 1000:
        return 0
    amount = random.randint(1, maxAmount)
    buyOfferData = {
        "company": companyId,
        "startAmount": amount,
        "amount": amount,
    }
    self.client.post("/api/addBuyOffer", headers={"authorization": "Token " + self.token}, json=buyOfferData, context={"userClass": self.userClass})
    return 1
    
def sellOffer(self, maxAmount,companyId = None):
    response = self.client.get("/api/user/stocks", headers={"authorization": "Token " + self.token}, context={"userClass": self.userClass})
    userStocks = response.json()
    userStocks.pop()
    if not userStocks:
        return 0
    if companyId == None:
        stock = random.choice(userStocks)
        companyId = stock['company']
    else:
        stock = next((s for s in userStocks if s['company'] == companyId), None)
        if stock is None:
            return 0
    availableAmount = stock['amount']
    if availableAmount == 0:
        return 0
    amountToSell = random.randint(1, min(availableAmount,maxAmount))
    sellOfferData = {
        "company": companyId,
        "startAmount": amountToSell,
        "amount": amountToSell,
    }
    self.client.post("/api/addSellOffer", headers={"authorization": "Token " + self.token}, json=sellOfferData, context={"userClass": self.userClass})
    return 1
    
class WebsiteReadOnlyUser(FastHttpUser):
    weight = 1
    wait_time = constant(timeBetweenRequests)
    token = ''
    userClass = 'WebsiteReadOnlyUser'
    
    def on_start(self):
        register(self)        

    @task
    def getSellOffers(self):
        self.client.get("/api/user/sellOffers", headers={"authorization": "Token " + self.token}, context={"userClass": self.userClass})
        
    @task()
    def wait(self):
        pass
        
    @task
    def getBuyOffers(self):
        self.client.get("/api/user/buyOffers", headers={"authorization": "Token " + self.token}, context={"userClass": self.userClass})
        
    @task
    def getStocks(self):
        self.client.get("/api/user/stocks", headers={"authorization": "Token " + self.token}, context={"userClass": self.userClass})
        
    @task
    def getCompanies(self):
        self.client.get("/api/companies",headers={"authorization": "Token " + self.token}, context={"userClass": self.userClass})
        
class WebsiteActiveUser(FastHttpUser):
    weight = 2
    wait_time = constant(timeBetweenRequests)
    token = ''
    userClass = 'WebsiteActiveUser'
    
    def on_start(self):
        register(self)

    @task
    def wait(self):
        pass
    
    @task
    def addSellOffer(self):
        sellOffer(self, 10)

    @task
    def addBuyOffer(self):
        response = self.client.get("/api/companies", headers={"authorization": "Token " + self.token}, context={"userClass": self.userClass})
        companies = response.json()    
        companies.pop()        
        if not companies:
            return
        company = random.choice(companies)
        companyId = company['id']
        buyOffer(self, companyId, 10)
                
class WebsiteActiveUserWtihMarketAnalize(FastHttpUser):
    weight = 2
    numberOfRates = 3
    wait_time = constant(timeBetweenRequests)
    token = ''
    limitNumerOfBuyOffersInOneTask = 2
    limitNumerOfSellOffersInOneTask = 3
    userClass = 'WebsiteActiveUserWtihMarketAnalize'
    
    def on_start(self):
        register(self)

    @task
    def wait(self):
        pass
    
    @task
    def checkOffers(self):
        numberOfBuyOffers = 0
        numberOfSellOffers = 0
        response = self.client.get("/api/getCompaniesStockRates", headers={"authorization": "Token " + self.token}, json={'numberOfRates' : self.numberOfRates}, context={"userClass": self.userClass})
        try:
            stockRates = response.json()
        except(ValueError, KeyError):
            return
        stockRates.pop()
        if not stockRates:
            return
        companiesStockRates = {}
        for rate in stockRates:
            companyId = rate['company']
            price = rate['rate']
            if companyId not in companiesStockRates:
                companiesStockRates[companyId] = []
            companiesStockRates[companyId].append(price)
        shuffledCompanies = list(companiesStockRates.keys())
        random.shuffle(shuffledCompanies)
        for companyId in shuffledCompanies:
            priceHistories = companiesStockRates[companyId]
            if numberOfBuyOffers >= self.limitNumerOfBuyOffersInOneTask and numberOfSellOffers >= self.limitNumerOfSellOffersInOneTask:
                return
            if len(priceHistories) < self.numberOfRates:
                continue
            priceTrend = self.getPriceTrend(list(reversed(priceHistories)))
            if priceTrend == "nierosnący" and numberOfBuyOffers < self.limitNumerOfBuyOffersInOneTask:
                numberOfBuyOffers += buyOffer(self, companyId, 3)            
            if priceTrend == "niemalejący" and numberOfSellOffers < self.limitNumerOfSellOffersInOneTask:
                numberOfSellOffers += sellOffer(self, 3, companyId=companyId)

    def getPriceTrend(self, priceHistory):
        isNiemalejący = all(x <= y for x, y in zip(priceHistory, priceHistory[1:]))
        isNierosnący = all(x >= y for x, y in zip(priceHistory, priceHistory[1:]))
        if isNiemalejący:
            return "niemalejący"
        elif isNierosnący:
            return "nierosnący"
        else:
            return None
           
    @events.request.add_listener
    def logRequest(request_type, name, response_time, response_length, response, context, exception, **kwargs):
        if exception:
            return
        if context:
            userClass = context["userClass"]
        else:
            userClass = 'WebsiteActiveUser'
        try:
            if isinstance(response.json(), list):
                id = response.json()[-1]["requestId"]
            else:
                id = response.json()['requestId']
        except (ValueError, KeyError):
            return
        timestamp = datetime.now()
        cursor.execute(
            """INSERT INTO "stockApp_trafficlog" (timestamp, "requestid", "apiTime","userClass") VALUES (%s, %s, %s,%s)""",
            (timestamp, id, response_time / 1000.0,userClass)
        )
        conn.commit()
    