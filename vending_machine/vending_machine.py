"""
Professional OOP Vending Machine
Run: python vending_machine.py

Concepts demonstrated:
- Encapsulation
- Inheritance and polymorphism
- Composition
- Exception handling
- Type hints and dataclasses
- Input validation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional


# ----------------------------- Custom Exceptions -----------------------------

class VendingMachineError(Exception):
    """Base exception for vending machine operations."""


class ProductNotFoundError(VendingMachineError):
    """Raised when a product ID does not exist."""


class OutOfStockError(VendingMachineError):
    """Raised when a product is unavailable."""


class InsufficientFundsError(VendingMachineError):
    """Raised when the customer has not paid enough."""


class InvalidPaymentError(VendingMachineError):
    """Raised when a payment amount is invalid."""


# --------------------------------- Models ------------------------------------

@dataclass
class Product:
    """Represents a product stocked in the vending machine."""

    product_id: str
    name: str
    price: Decimal
    quantity: int

    def __post_init__(self) -> None:
        self.product_id = self.product_id.strip().upper()
        self.name = self.name.strip()

        if not self.product_id:
            raise ValueError("Product ID cannot be empty.")
        if not self.name:
            raise ValueError("Product name cannot be empty.")
        if self.price <= Decimal("0"):
            raise ValueError("Product price must be greater than zero.")
        if self.quantity < 0:
            raise ValueError("Product quantity cannot be negative.")

    @property
    def in_stock(self) -> bool:
        return self.quantity > 0

    def reduce_stock(self, amount: int = 1) -> None:
        if amount <= 0:
            raise ValueError("Stock reduction must be positive.")
        if self.quantity < amount:
            raise OutOfStockError(f"{self.name} is out of stock.")
        self.quantity -= amount

    def add_stock(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("Restock quantity must be positive.")
        self.quantity += amount


@dataclass
class Transaction:
    """Records a completed purchase."""

    timestamp: datetime
    product_id: str
    product_name: str
    price: Decimal
    amount_paid: Decimal
    change_returned: Decimal

    @property
    def formatted_time(self) -> str:
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------- Payment System ------------------------------

class PaymentProcessor:
    """Validates payments and calculates change."""

    def process_payment(self, price: Decimal, amount_paid: Decimal) -> Decimal:
        if amount_paid <= Decimal("0"):
            raise InvalidPaymentError("Payment must be greater than zero.")

        if amount_paid < price:
            raise InsufficientFundsError(
                f"Insufficient payment. Product costs ₹{price:.2f}, "
                f"but you entered ₹{amount_paid:.2f}."
            )

        return amount_paid - price


# ------------------------------ Vending Machine ------------------------------

class VendingMachine:
    """Coordinates inventory, payment, purchases, and sales reporting."""

    def __init__(
        self,
        products: Optional[List[Product]] = None,
        payment_processor: Optional[PaymentProcessor] = None,
    ) -> None:
        self._inventory: Dict[str, Product] = {}
        self._transactions: List[Transaction] = []
        self._payment_processor = payment_processor or PaymentProcessor()

        if products:
            for product in products:
                self.add_product(product)

    def add_product(self, product: Product) -> None:
        product_id = product.product_id.upper()
        if product_id in self._inventory:
            raise ValueError(f"Product ID {product_id} already exists.")
        self._inventory[product_id] = product

    def display_products(self) -> None:
        print("\n" + "=" * 62)
        print("                  AVAILABLE PRODUCTS")
        print("=" * 62)
        print(f"{'ID':<8}{'Product':<24}{'Price':>12}{'Stock':>12}")
        print("-" * 62)

        for product in self._inventory.values():
            stock_label = str(product.quantity) if product.in_stock else "SOLD OUT"
            print(
                f"{product.product_id:<8}"
                f"{product.name:<24}"
                f"₹{product.price:>10.2f}"
                f"{stock_label:>12}"
            )

        print("=" * 62)

    def get_product(self, product_id: str) -> Product:
        key = product_id.strip().upper()
        product = self._inventory.get(key)
        if product is None:
            raise ProductNotFoundError(
                f"No product found with ID '{key}'. Please check the ID."
            )
        return product

    def purchase(self, product_id: str, amount_paid: Decimal) -> Transaction:
        """
        Complete a purchase.

        Stock and transaction history are changed only after payment succeeds.
        """
        product = self.get_product(product_id)

        if not product.in_stock:
            raise OutOfStockError(f"Sorry, {product.name} is out of stock.")

        change = self._payment_processor.process_payment(product.price, amount_paid)

        # Commit the purchase only after all checks pass.
        product.reduce_stock()
        transaction = Transaction(
            timestamp=datetime.now(),
            product_id=product.product_id,
            product_name=product.name,
            price=product.price,
            amount_paid=amount_paid,
            change_returned=change,
        )
        self._transactions.append(transaction)
        return transaction

    def restock_product(self, product_id: str, quantity: int) -> None:
        product = self.get_product(product_id)
        product.add_stock(quantity)
        print(f"Restocked {quantity} unit(s) of {product.name}.")

    def display_sales_report(self) -> None:
        total_sales = sum(
            (transaction.price for transaction in self._transactions),
            start=Decimal("0"),
        )

        print("\n" + "=" * 48)
        print("                  SALES REPORT")
        print("=" * 48)
        print(f"Completed purchases : {len(self._transactions)}")
        print(f"Total sales         : ₹{total_sales:.2f}")

        if not self._transactions:
            print("No purchases have been completed yet.")
        else:
            print("\nRecent transactions:")
            for transaction in self._transactions[-10:]:
                print(
                    f"{transaction.formatted_time} | "
                    f"{transaction.product_name} | "
                    f"₹{transaction.price:.2f} | "
                    f"Change: ₹{transaction.change_returned:.2f}"
                )
        print("=" * 48)


# ----------------------------- User Interfaces -------------------------------

class VendingMachineApp:
    """Terminal user interface for customers and administrators."""

    ADMIN_PIN = "2468"  # Demo only; use secure authentication in real systems.

    def __init__(self, machine: VendingMachine) -> None:
        self._machine = machine

    @staticmethod
    def _read_money(prompt: str) -> Decimal:
        raw_value = input(prompt).strip().replace("₹", "").replace(",", "")
        try:
            amount = Decimal(raw_value)
        except InvalidOperation as exc:
            raise InvalidPaymentError(
                "Please enter a valid amount, for example 20 or 20.50."
            ) from exc

        if not amount.is_finite():
            raise InvalidPaymentError("Please enter a valid finite amount.")
        if amount <= Decimal("0"):
            raise InvalidPaymentError("Amount must be greater than zero.")
        return amount.quantize(Decimal("0.01"))

    def customer_menu(self) -> None:
        while True:
            print("\n--- CUSTOMER MENU ---")
            print("1. View products")
            print("2. Buy a product")
            print("3. Back to main menu")

            choice = input("Choose an option: ").strip()

            if choice == "1":
                self._machine.display_products()
            elif choice == "2":
                self._buy_product()
            elif choice == "3":
                return
            else:
                print("Invalid choice. Please select 1, 2, or 3.")

    def _buy_product(self) -> None:
        self._machine.display_products()
        product_id = input("Enter the product ID: ").strip()

        try:
            product = self._machine.get_product(product_id)
            if not product.in_stock:
                raise OutOfStockError(f"Sorry, {product.name} is out of stock.")

            print(f"\nSelected: {product.name}")
            print(f"Price: ₹{product.price:.2f}")
            amount_paid = self._read_money("Enter payment amount (₹): ")

            transaction = self._machine.purchase(product_id, amount_paid)

            print("\n" + "-" * 40)
            print("             PURCHASE SUCCESSFUL")
            print("-" * 40)
            print(f"Product : {transaction.product_name}")
            print(f"Paid    : ₹{transaction.amount_paid:.2f}")
            print(f"Price   : ₹{transaction.price:.2f}")
            print(f"Change  : ₹{transaction.change_returned:.2f}")
            print("Please collect your product and change.")
            print("-" * 40)

        except VendingMachineError as error:
            print(f"\nPurchase failed: {error}")
        except ValueError as error:
            print(f"\nInvalid input: {error}")

    def admin_menu(self) -> None:
        pin = input("Enter administrator PIN: ").strip()
        if pin != self.ADMIN_PIN:
            print("Access denied. Incorrect PIN.")
            return

        while True:
            print("\n--- ADMIN MENU ---")
            print("1. View inventory")
            print("2. Restock product")
            print("3. View sales report")
            print("4. Back to main menu")

            choice = input("Choose an option: ").strip()

            if choice == "1":
                self._machine.display_products()
            elif choice == "2":
                self._restock_product()
            elif choice == "3":
                self._machine.display_sales_report()
            elif choice == "4":
                return
            else:
                print("Invalid choice. Please select 1, 2, 3, or 4.")

    def _restock_product(self) -> None:
        self._machine.display_products()
        product_id = input("Enter product ID to restock: ").strip()

        try:
            quantity_text = input("Enter quantity to add: ").strip()
            quantity = int(quantity_text)
            self._machine.restock_product(product_id, quantity)
        except ValueError as error:
            print(f"Invalid quantity: {error}")
        except VendingMachineError as error:
            print(f"Restocking failed: {error}")

    def run(self) -> None:
        print("\n" + "=" * 48)
        print("        WELCOME TO PYTHON VENDING MACHINE")
        print("=" * 48)

        while True:
            print("\nMAIN MENU")
            print("1. Customer")
            print("2. Administrator")
            print("3. Exit")

            choice = input("Choose an option: ").strip()

            if choice == "1":
                self.customer_menu()
            elif choice == "2":
                self.admin_menu()
            elif choice == "3":
                print("Thank you for using our vending machine. Goodbye!")
                break
            else:
                print("Invalid choice. Please select 1, 2, or 3.")


# --------------------------------- Entry Point -------------------------------

def create_default_machine() -> VendingMachine:
    """Create a machine with sample products and starting stock."""
    products = [
        Product("A1", "Water Bottle", Decimal("20.00"), 10),
        Product("A2", "Coca-Cola", Decimal("40.00"), 8),
        Product("A3", "Potato Chips", Decimal("30.00"), 12),
        Product("A4", "Chocolate Bar", Decimal("25.00"), 15),
        Product("A5", "Biscuits", Decimal("10.00"), 20),
        Product("A6", "Orange Juice", Decimal("50.00"), 6),
    ]
    return VendingMachine(products=products)


def main() -> None:
    machine = create_default_machine()
    app = VendingMachineApp(machine)
    try:
        app.run()
    except (KeyboardInterrupt, EOFError):
        print("\n\nApplication closed safely. Goodbye!")


if __name__ == "__main__":
    main()
