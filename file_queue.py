class Queue:
    def __init__(self):
        self.items = []

    def enqueue(self, item):
        """
        Ajoute un element a la fin de la file.
        """
        self.items.append(item)

    def dequeue(self):
        """
        Retire et retourne le premier element de la file.
        Si la file est vide, retourne None.
        """
        if not self.items:
            return None
        return self.items.pop(0)