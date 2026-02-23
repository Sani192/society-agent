#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 11:11:41 2026

@author: anonymous
"""

# app/modules/users/user_query_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import (
    EventFoodPass,
    Payment,
    Refund
)


class UserQueryService:

    @staticmethod
    def get_my_pass(db: Session, *, event_id, flat_id):
        return (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.flat_id == flat_id
            )
            .first()
        )

    @staticmethod
    def get_my_payment_summary(db: Session, *, event_id, flat_id):
        paid = (
            db.query(func.coalesce(func.sum(Payment.paid_amount), 0))
            .filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat_id
            )
            .scalar()
        )

        refunded = (
            db.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(
                Refund.event_id == event_id,
                Refund.flat_id == flat_id,
                Refund.status == "refunded"
            )
            .scalar()
        )

        return {
            "paid": paid,
            "refunded": refunded,
            "net_paid": paid - refunded
        }

    @staticmethod
    def get_my_balance(db: Session, *, event_id, flat_id):
        food_pass = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.flat_id == flat_id
            )
            .first()
        )

        expected_amount = food_pass.total_amount if food_pass else 0

        paid_amount = (
            db.query(func.coalesce(func.sum(Payment.paid_amount), 0))
            .filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat_id
            )
            .scalar()
        )

        refunded_amount = (
            db.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(
                Refund.event_id == event_id,
                Refund.flat_id == flat_id,
                Refund.status == "refunded"
            )
            .scalar()
        )

        balance = expected_amount - paid_amount - refunded_amount
        if balance < 0:
            balance = 0

        return {
            "expected": expected_amount,
            "paid": paid_amount,
            "balance": balance
        }

    @staticmethod
    def get_my_status(db: Session, *, event_id, flat_id):
        food_pass = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.flat_id == flat_id
            )
            .first()
        )

        if not food_pass:
            return "Not participating"

        total = (
            food_pass.veg_count +
            food_pass.jain_count +
            food_pass.kids_count
        )

        return "Participating" if total > 0 else "Not participating"
