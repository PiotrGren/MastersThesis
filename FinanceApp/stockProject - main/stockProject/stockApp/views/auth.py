from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from stockApp.models import CustomUser
from stockApp.serializers import CustomUserSerializer
from rest_framework.authtoken.models import Token
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
import uuid

@api_view(['POST'])
@permission_classes([AllowAny])
def signUp(request):
    serializer = CustomUserSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data.get('username')
        email = serializer.validated_data.get('email')
        if CustomUser.objects.filter(username=username).exists():
            return Response({'error': 'User with this username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        if CustomUser.objects.filter(email=email).exists():
            return Response({'error': 'User with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        requestId = str(uuid.uuid4())
        return Response({'message': 'User created successfully.','requestId':requestId}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def signIn(request):
    username = request.data['username']
    password = request.data['password']
    if username is None or password is None:
        return Response({'error': 'Please provide both username and password'}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    
    if user is not None:
        token, created = Token.objects.get_or_create(user=user)
        requestId = str(uuid.uuid4())
        return Response({'token': token.key, 'requestId':requestId}, status=status.HTTP_200_OK)
    else:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)