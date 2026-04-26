"""User persona definitions — behavioral profiles for simulation.

Each persona defines what actions a simulated user takes, how many products
they browse, whether they add to cart, complete checkout, etc.
"""

from dataclasses import dataclass, field
import random


@dataclass
class Persona:
    name: str
    weight: float  # Fraction of users assigned this persona (sums to 1.0)

    # Browse behavior
    products_to_view: tuple[int, int]  # (min, max) products to browse
    categories_to_browse: int  # Number of categories to visit
    searches: int  # Number of product searches
    uses_filter: bool  # Whether user applies category/sort filters

    # Cart behavior
    adds_to_cart: bool
    cart_items: tuple[int, int]  # (min, max) items to add
    changes_quantity: bool  # Whether user modifies cart quantities
    removes_item: bool  # Whether user removes an item from cart

    # Checkout behavior
    starts_checkout: bool
    completes_payment: bool
    intentional_decline: bool  # Use pm_card_declined for testing failures
    uses_coupon: bool

    # Session behavior
    session_duration_min: tuple[int, int]  # (min, max) simulated minutes
    return_visits: int  # 0 = single session
    orders: int  # Total orders to complete (power_buyer > 1)

    # Wishlist
    uses_wishlist: bool
    moves_wishlist_to_cart: bool

    # Subscription
    subscribes: bool


PERSONAS: list[Persona] = [
    Persona(
        name="window_shopper",
        weight=0.30,
        products_to_view=(5, 15),
        categories_to_browse=2,
        searches=2,
        uses_filter=True,
        adds_to_cart=False,
        cart_items=(0, 0),
        changes_quantity=False,
        removes_item=False,
        starts_checkout=False,
        completes_payment=False,
        intentional_decline=False,
        uses_coupon=False,
        session_duration_min=(3, 8),
        return_visits=0,
        orders=0,
        uses_wishlist=True,
        moves_wishlist_to_cart=False,
        subscribes=False,
    ),
    Persona(
        name="cart_abandoner",
        weight=0.20,
        products_to_view=(3, 8),
        categories_to_browse=1,
        searches=1,
        uses_filter=False,
        adds_to_cart=True,
        cart_items=(1, 3),
        changes_quantity=True,
        removes_item=False,
        starts_checkout=True,
        completes_payment=False,
        intentional_decline=False,
        uses_coupon=False,
        session_duration_min=(5, 12),
        return_visits=0,
        orders=0,
        uses_wishlist=False,
        moves_wishlist_to_cart=False,
        subscribes=False,
    ),
    Persona(
        name="single_buyer",
        weight=0.25,
        products_to_view=(2, 5),
        categories_to_browse=1,
        searches=1,
        uses_filter=False,
        adds_to_cart=True,
        cart_items=(1, 2),
        changes_quantity=False,
        removes_item=False,
        starts_checkout=True,
        completes_payment=True,
        intentional_decline=False,
        uses_coupon=False,
        session_duration_min=(8, 15),
        return_visits=0,
        orders=1,
        uses_wishlist=False,
        moves_wishlist_to_cart=False,
        subscribes=False,
    ),
    Persona(
        name="power_buyer",
        weight=0.10,
        products_to_view=(10, 20),
        categories_to_browse=3,
        searches=3,
        uses_filter=True,
        adds_to_cart=True,
        cart_items=(2, 5),
        changes_quantity=True,
        removes_item=True,
        starts_checkout=True,
        completes_payment=True,
        intentional_decline=False,
        uses_coupon=True,
        session_duration_min=(15, 30),
        return_visits=random.randint(2, 3),
        orders=random.randint(2, 4),
        uses_wishlist=True,
        moves_wishlist_to_cart=True,
        subscribes=False,
    ),
    Persona(
        name="subscriber",
        weight=0.10,
        products_to_view=(1, 3),
        categories_to_browse=0,
        searches=0,
        uses_filter=False,
        adds_to_cart=True,  # Subscription added to cart
        cart_items=(1, 1),
        changes_quantity=False,
        removes_item=False,
        starts_checkout=True,
        completes_payment=True,
        intentional_decline=False,
        uses_coupon=False,
        session_duration_min=(5, 10),
        return_visits=0,
        orders=1,
        uses_wishlist=False,
        moves_wishlist_to_cart=False,
        subscribes=True,
    ),
    Persona(
        name="bouncer",
        weight=0.05,
        products_to_view=(1, 2),
        categories_to_browse=0,
        searches=0,
        uses_filter=False,
        adds_to_cart=False,
        cart_items=(0, 0),
        changes_quantity=False,
        removes_item=False,
        starts_checkout=False,
        completes_payment=False,
        intentional_decline=False,
        uses_coupon=False,
        session_duration_min=(1, 3),
        return_visits=0,
        orders=0,
        uses_wishlist=False,
        moves_wishlist_to_cart=False,
        subscribes=False,
    ),
]


def assign_personas(user_count: int) -> list[Persona]:
    """Assign personas to N users based on weight distribution."""
    assigned: list[Persona] = []
    remaining = user_count

    for i, persona in enumerate(PERSONAS):
        if i == len(PERSONAS) - 1:
            # Last persona gets whatever is left
            count = remaining
        else:
            count = round(persona.weight * user_count)
            remaining -= count

        for _ in range(count):
            # Create a fresh copy with randomized fields
            p = Persona(
                name=persona.name,
                weight=persona.weight,
                products_to_view=persona.products_to_view,
                categories_to_browse=persona.categories_to_browse,
                searches=persona.searches,
                uses_filter=persona.uses_filter,
                adds_to_cart=persona.adds_to_cart,
                cart_items=persona.cart_items,
                changes_quantity=persona.changes_quantity,
                removes_item=persona.removes_item,
                starts_checkout=persona.starts_checkout,
                completes_payment=persona.completes_payment,
                intentional_decline=persona.intentional_decline,
                uses_coupon=persona.uses_coupon,
                session_duration_min=persona.session_duration_min,
                return_visits=persona.return_visits if persona.return_visits else 0,
                orders=persona.orders if persona.orders else 0,
                uses_wishlist=persona.uses_wishlist,
                moves_wishlist_to_cart=persona.moves_wishlist_to_cart,
                subscribes=persona.subscribes,
            )
            assigned.append(p)

    random.shuffle(assigned)
    return assigned[:user_count]


# Add a few intentional payment declines to single_buyer pool
def inject_declines(personas: list[Persona], decline_rate: float = 0.05) -> None:
    """Mark ~5% of buyers for intentional payment decline."""
    buyers = [p for p in personas if p.completes_payment and not p.subscribes]
    decline_count = max(1, round(len(buyers) * decline_rate))
    for p in random.sample(buyers, min(decline_count, len(buyers))):
        p.intentional_decline = True
        p.completes_payment = False  # Will attempt but fail
