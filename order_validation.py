"""Reusable validation for order-entry values."""

from collections.abc import Collection


def validate_existing_id(
    value: str, valid_ids: Collection[int], record_type: str
) -> int:
    """Return an integer ID if it exists, otherwise raise a helpful ValueError."""
    try:
        record_id = int(value.strip())
    except ValueError:
        raise ValueError(f"Enter a whole-number {record_type} ID.") from None

    if record_id not in valid_ids:
        raise ValueError(
            f"No matching {record_type} ID. Choose an ID from the table."
        )
    return record_id


def validate_quantity(value: str) -> int:
    """Return a positive whole-number quantity or raise a helpful ValueError."""
    cleaned_value = value.strip()
    if not cleaned_value.isdecimal():
        raise ValueError("Enter a whole-number quantity greater than zero.")

    quantity = int(cleaned_value)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    return quantity


def validate_confirmation(value: str) -> bool:
    """Return True for yes, False for no, and reject other responses."""
    answer = value.strip().casefold()
    if answer == "y":
        return True
    if answer == "n":
        return False
    raise ValueError("Enter Y to confirm or N to cancel.")


def ask_for_existing_id(
    prompt: str, valid_ids: Collection[int], record_type: str
) -> int:
    """Prompt until the user enters an ID that exists in the database."""
    while True:
        try:
            return validate_existing_id(input(prompt), valid_ids, record_type)
        except ValueError as error:
            print(error)


def ask_for_quantity() -> int:
    """Prompt until the user enters a positive whole number."""
    while True:
        try:
            return validate_quantity(input("Quantity: "))
        except ValueError as error:
            print(error)


def ask_for_confirmation() -> bool:
    """Prompt until the user confirms or cancels the order."""
    while True:
        try:
            return validate_confirmation(input("Confirm order? (Y/N): "))
        except ValueError as error:
            print(error)
