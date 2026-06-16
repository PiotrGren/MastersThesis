from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from stockApp.models import CustomUser
from stockApp.serializers import CustomUserSerializer
from stockApp.views.mixins import RequestContextMixin


class SignUpView(RequestContextMixin, APIView):
    """
    POST /api/signUp
    Tworzy nowego użytkownika.
    Zwraca: {"message": "User created successfully."} przy 201
    (Bez requestId w body - X-Request-ID dołoży middleware w nagłówku.)
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = CustomUserSerializer(data=request.data, context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data.get("username")    # type: ignore[reportOptionalMemberAccess]
        email = serializer.validated_data.get("email")          # type: ignore[reportOptionalMemberAccess]
        if CustomUser.objects.filter(username=username).exists():
            return Response({"error": "User with this username already exists."},
                            status=status.HTTP_400_BAD_REQUEST)
        if email and CustomUser.objects.filter(email=email).exists():
            return Response({"error": "User with this email already exists."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response({"message": "User created successfully."}, status=status.HTTP_201_CREATED)


class SignInView(RequestContextMixin, APIView):
    """
    POST /api/signIn
    Autoryzuje użytkownika i zwraca token.
    Zwraca: {"token": "<token>"} przy 200 albo {"error": "..."} przy 400.
    (Bez requestId w body - X-Request-ID dołoży middleware w nagłówku.)
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key}, status=status.HTTP_200_OK)

















"""
OLD

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
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)"""