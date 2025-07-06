import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURAZIONE ---

# Variabili d'ambiente (Render)
GOOGLE_SHEET1_ID = os.environ.get('GOOGLE_SHEET1_ID')  # ID foglio Sheet1 (lead)
GOOGLE_SHEET2_ID = os.environ.get('GOOGLE_SHEET2_ID')  # ID foglio Sheet2 (buyer)
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID')

# Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Flask
app = Flask(__name__)
CORS(app)

# --- Google Sheets Setup ---

def get_gspread_client():
    print('=== GET_GSPREAD_CLIENT CALLED ===')
    # Get service account credentials from environment variable
    service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    print('Service account JSON exists:', bool(service_account_json))
    
    if not service_account_json:
        raise Exception("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")
    
    try:
        creds_dict = json.loads(service_account_json)
        print('JSON parsed successfully')
        creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        print('Credentials created successfully')
        
        client = gspread.authorize(creds)
        print('GSpread client authorized successfully')
        return client
    except Exception as e:
        print('Error in get_gspread_client:', str(e))
        raise e

def get_worksheet(sheet_id, sheet_name):
    gc = get_gspread_client()
    sh = gc.open_by_key(sheet_id)
    return sh.worksheet(sheet_name)

# --- API ENDPOINTS ---

@app.route('/api/submit-form', methods=['POST'])
def submit_form():
    print('=== SUBMIT FORM CALLED ===')
    data = request.get_json()
    print('Received data:', data)
    
    try:
        print('Getting worksheet...')
        ws = get_worksheet(GOOGLE_SHEET1_ID, 'Sheet1')
        print('Worksheet obtained successfully')
        
        # Prepara i dati
        formattedTimestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        formattedBirthDate = data.get('birthDate', '')
        values = [
            formattedTimestamp,  # A: Timestamp
            data.get('firstName', ''),  # B: Nome
            data.get('lastName', ''),   # C: Cognome
            data.get('gender', ''),     # D: Preferenze
            data.get('zodiacSign', ''), # E: Segno zodiacale
            formattedBirthDate,          # F: Data nascita
            'Single',                    # G: Stato civile
            data.get('city', ''),        # H: Città
            data.get('email', ''),       # I: Email
            'LEAD'                       # J: Status
        ]
        print('Values to insert:', values)
        
        ws.append_row(values)
        print('Row appended successfully')
        return jsonify({'success': True, 'message': 'Form submitted successfully'})
    except Exception as e:
        print('Error submitting to Google Sheets:', str(e))
        print('Error type:', type(e))
        import traceback
        print('Full traceback:', traceback.format_exc())
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout():
    data = request.get_json()
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='payment',
            customer_email=data.get('email'),
            metadata={
                'firstName': data.get('firstName', ''),
                'lastName': data.get('lastName', ''),
                'email': data.get('email', ''),
                'gender': data.get('gender', ''),
                'birthDate': data.get('birthDate', ''),
                'zodiacSign': data.get('zodiacSign', ''),
                'country': data.get('country', ''),
                'city': data.get('city', ''),
                'timestamp': datetime.now().isoformat()
            },
            success_url=data.get('successUrl', 'https://divinesoulmate.vercel.app/success?session_id={CHECKOUT_SESSION_ID}'),
            cancel_url=data.get('cancelUrl', 'https://divinesoulmate.vercel.app/cancel'),
        )
        return jsonify({'url': session.url})
    except Exception as e:
        print('Error creating Stripe session:', e)
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/payment-success', methods=['POST'])
def payment_success():
    data = request.get_json()
    session_id = data.get('sessionId')
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != 'paid':
            return jsonify({'success': False, 'message': 'Payment not completed'}), 400
        metadata = session.metadata
        ws = get_worksheet(GOOGLE_SHEET2_ID, 'Sheet1')
        purchaseDate = datetime.now().strftime('%d/%m/%Y')
        purchaseTime = datetime.now().strftime('%H:%M:%S')
        values = [
            purchaseDate,                # A: Data acquisto
            purchaseTime,                # B: Orario
            session.id,                  # C: Codice acquisto
            '',
            'Divine Soulmate Reading',   # D: Nome prodotto
            1,                           # E: Quantità
            '', '', '', '', '',          # F-J: Colonne vuote
            metadata.get('lastName', ''),# K: Cognome
            metadata.get('firstName', ''),# L: Nome
            metadata.get('email', ''),   # M: Email
            '',                          # N: Spazio vuoto
            metadata.get('country', ''), # O: Paese
            'buyer'                      # P: Status
        ]
        ws.append_row(values)
        return jsonify({'success': True, 'message': 'Payment processed successfully'})
    except Exception as e:
        print('Error processing payment success:', e)
        return jsonify({'success': False, 'message': str(e)}), 500

# --- MAIN ---

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000))) 