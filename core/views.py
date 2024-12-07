from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import ChatMessage, Room, Booking, Payment, Billing
from django.contrib import messages
from django.views import View
from django.contrib.auth.models import User  
from datetime import datetime
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa


# Home view
def home(request):
    return render(request, 'home.html')

# Signup view
def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return redirect('login')  # Redirect back to the signup page

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('signup')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        messages.success(request, "Signup successful! Please log in.")
        return redirect('login')  # Redirect to the login page

    return render(request, 'signup.html')

# Login view
def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect('rooms')
        else:
            messages.error(request, "Invalid credentials! Please try again.")
    return render(request, 'login.html')

# View available rooms
@login_required(login_url='login') 
def available_rooms(request):
    rooms = Room.objects.filter(available=True)
    return render(request, 'available_rooms.html', {'rooms': rooms})

# View room details
def room_details(request, room_id):
    room = get_object_or_404(Room, id=room_id)  # Fetch room by ID or return 404 if not found
    return render(request, 'room_details.html', {'room': room})

# Book a room
@login_required
def book_room(request, room_id):
    room = get_object_or_404(Room, id=room_id)

    if room.is_booked:
        messages.error(request, 'This room is already booked. Please choose another room.')
        return redirect('rooms')  # Redirect to the rooms page

    if request.method == 'POST':
        check_in_date = request.POST.get('check_in_date')
        check_out_date = request.POST.get('check_out_date')
        number_of_guests = request.POST.get('number_of_guests')

        nights = (datetime.strptime(check_out_date, '%Y-%m-%d') - datetime.strptime(check_in_date, '%Y-%m-%d')).days
        total_price = room.price_per_night * nights if nights > 0 else 0

        check_in_date = datetime.strptime(check_in_date, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out_date, '%Y-%m-%d').date()

        booking = Booking(
            room=room,
            user=request.user,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            number_of_guests=number_of_guests,
            total_price=total_price
        )
        booking.save()

        room.is_booked = True
        room.save()

        return redirect('booking_success')  # Redirect to a success page

    return render(request, 'book_room.html', {'room': room})

# Booking success page
def booking_success(request):
    latest_booking = Booking.objects.filter(user=request.user).order_by('-created_at').first()
    return render(request, 'booking_success.html', {'booking': latest_booking})

# Process payment
def process_payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    
    if request.method == 'POST':
        payment_amount = booking.total_price
        payment_method = request.POST.get('payment_method')  # e.g., from a form
        payment_reference = request.POST.get('payment_reference')  # Unique reference from payment processor

        # Create payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=payment_amount,
            payment_method=payment_method,
            payment_status='paid',  # Initially set to pending
            payment_reference=payment_reference,
        )

        # Create or update billing record
        billing, created = Billing.objects.get_or_create(
            user=request.user,
            booking=booking,
            defaults={'amount': payment_amount, 'status': 'Paid'}  # Mark as paid on creation
        )

        # If billing already exists, just update the status if necessary
        if not created:
            billing.amount = payment_amount
            billing.status = 'Paid'  # Update status if needed
            billing.save()

        return redirect('payment_success', payment_id=payment.id)

    return render(request, 'payment.html', {'booking': booking})

# Payment success view
class PaymentSuccessView(View):
    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        return render(request, 'payment_success.html', {'payment': payment})

# User dashboard
from .models import Booking, Receipt, ChatMessage
from django.db.models import Sum

@login_required
def dashboard(request):
    # Get the current user's bookings, receipts, and chat messages
    bookings = Booking.objects.filter(user=request.user)
    receipts = Receipt.objects.filter(user=request.user)
    chat_messages = ChatMessage.objects.filter(user=request.user)

    # Calculate total amount paid by the user
    total_paid = Payment.objects.filter(booking__user=request.user, payment_status='completed').aggregate(total=Sum('amount'))['total'] or 0

    # Get payment details
    payments = Payment.objects.filter(booking__user=request.user)

    # Calculate total number of bookings
    total_bookings = bookings.count()

    # Aggregate check-ins and check-outs
    checkins = bookings.values('check_in_date').distinct()
    checkouts = bookings.values('check_out_date').distinct()

    # Additional data can be added here as needed
    return render(request, 'dashboard.html', {
        'bookings': bookings,
        'receipts': receipts,
        'chat_messages': chat_messages,
        'total_paid': total_paid,
        'payments': payments,
        'total_bookings': total_bookings,
        'checkins': checkins,
        'checkouts': checkouts,
    })

# Cancel booking
@login_required
def cancel_booking(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
        booking.delete()
        messages.success(request, 'Booking cancelled successfully.')
        return redirect('dashboard')  # Redirect to dashboard after canceling
    except Booking.DoesNotExist:
        messages.error(request, 'Booking not found.')
        return redirect('dashboard')


# Cancel booking 
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    booking.is_cancelled = True
    booking.save()
    return redirect('dashboard')
    booking = Booking.objects.get(id=booking_id)
    booking.status = 'Cancelled'
    booking.save()
    return redirect('dashboard')

def send_message(request):
    if request.method == 'POST':
        user_message = request.POST['user_message']
        chat_message = ChatMessage(user=request.user, user_message=user_message, admin_message="Admin will respond soon.")
        chat_message.save()
    return redirect('dashboard')

# Generate receipt
def download_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id, user=request.user)
    # Assuming the receipt is stored as a PDF or image file
    with open(receipt.file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{receipt.booking.id}_receipt.pdf"'
        return response
    
   
