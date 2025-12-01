# Example: Integrate with deposit service
# funds/services/crypto_deposit_service.py

import uuid
from django.utils import timezone
from funds.models import Transaction, Wallet
from notifications.services import NotificationService
from django.db import transaction


def _credit_wallet(self, user, currency, amount, tx_hash):
    """Credit user's wallet after confirmed deposit"""
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(
            user=user,
            currency=currency
        )
        
        wallet.balance += amount
        wallet.save()
        
        Transaction.objects.create(
            user=user,
            transaction_type='deposit',
            currency=currency,
            amount=amount,
            status='completed',
            reference_id=f'CRYPTO-DEP-{uuid.uuid4().hex[:12]}',
            external_id=tx_hash,
            completed_at=timezone.now()
        )
        
        # CREATE NOTIFICATION
        NotificationService.notify_deposit(
            user=user,
            amount=amount,
            currency=currency,
            tx_hash=tx_hash
        )