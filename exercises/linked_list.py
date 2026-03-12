"""LinkedList — implémentation singly linked list."""
from __future__ import annotations


class Node:
    __slots__ = ("value", "next")

    def __init__(self, value, next_node: Node | None = None):
        self.value = value
        self.next = next_node


class LinkedList:
    def __init__(self):
        self.head: Node | None = None
        self._size: int = 0

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        parts = []
        current = self.head
        while current:
            parts.append(repr(current.value))
            current = current.next
        return " -> ".join(parts) + " -> None"

    def __iter__(self):
        current = self.head
        while current:
            yield current.value
            current = current.next

    def __contains__(self, value) -> bool:
        return any(v == value for v in self)

    # ── Insertion ──────────────────────────────

    def prepend(self, value) -> None:
        """Insère en tête — O(1)."""
        self.head = Node(value, self.head)
        self._size += 1

    def append(self, value) -> None:
        """Insère en queue — O(n)."""
        new_node = Node(value)
        if not self.head:
            self.head = new_node
        else:
            current = self.head
            while current.next:
                current = current.next
            current.next = new_node
        self._size += 1

    def insert_at(self, index: int, value) -> None:
        """Insère à la position donnée — O(n)."""
        if index <= 0:
            self.prepend(value)
            return
        if index >= self._size:
            self.append(value)
            return
        current = self.head
        for _ in range(index - 1):
            current = current.next
        current.next = Node(value, current.next)
        self._size += 1

    # ── Suppression ────────────────────────────

    def pop_front(self):
        """Retire et retourne la tête — O(1)."""
        if not self.head:
            raise IndexError("pop from empty list")
        value = self.head.value
        self.head = self.head.next
        self._size -= 1
        return value

    def remove(self, value) -> bool:
        """Supprime la première occurrence — O(n). Retourne True si trouvé."""
        if not self.head:
            return False
        if self.head.value == value:
            self.head = self.head.next
            self._size -= 1
            return True
        current = self.head
        while current.next:
            if current.next.value == value:
                current.next = current.next.next
                self._size -= 1
                return True
            current = current.next
        return False

    # ── Accès ──────────────────────────────────

    def get(self, index: int):
        """Accès par index — O(n)."""
        if index < 0 or index >= self._size:
            raise IndexError(f"index {index} out of range")
        current = self.head
        for _ in range(index):
            current = current.next
        return current.value

    # ── Utilitaires ────────────────────────────

    def reverse(self) -> None:
        """Inverse la liste en place — O(n)."""
        prev = None
        current = self.head
        while current:
            next_node = current.next
            current.next = prev
            prev = current
            current = next_node
        self.head = prev

    def clear(self) -> None:
        self.head = None
        self._size = 0


if __name__ == "__main__":
    ll = LinkedList()
    for x in [10, 20, 30, 40]:
        ll.append(x)
    print(f"Liste:    {ll}")
    print(f"Taille:   {len(ll)}")
    print(f"30 in ll: {30 in ll}")

    ll.reverse()
    print(f"Reversed: {ll}")

    ll.remove(20)
    print(f"Remove 20: {ll}")
