# stockApp/middleware/LogRequestMiddleware.py
import datetime
import time
from django.utils.deprecation import MiddlewareMixin
from django.db import connection
from stockApp.models import MarketLog

class LogRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.startTime = time.time()

    def process_response(self, request, response):
        if request.get_full_path() == '/api/deleteDb':
            return response
        if hasattr(request, 'startTime') and hasattr(response, 'data'):
            totalTime = time.time() - request.startTime
            dbtime = sum(float(query['time']) for query in connection.queries)
            id = None
            if isinstance(response.data, list) and 'requestId' in response.data[-1]:
                id = response.data[-1]["requestId"]
            if isinstance(response.data, dict) and 'requestId' in response.data:
                id = response.data['requestId']
            if id:
                MarketLog.objects.using('test').create(
                    apiMethod=request.method,
                    applicationTime=totalTime,
                    databaseTime=dbtime,
                    endpointUrl=request.get_full_path(),
                    requestId=id,
                    timestamp = datetime.datetime.now()
                )

        return response
