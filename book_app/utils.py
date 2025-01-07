from .models import Copy, Rental

def add_copies(book, quantity):
    """
    Kitob uchun yangi nusxalar qo'shish va `inventory_number`ni kitobga nisbatan unik qilish.
    """
    # Mavjud eng katta inventar raqamini olish
    last_copy = Copy.objects.filter(book=book).order_by("-inventory_number").first()

    if last_copy and last_copy.inventory_number.isdigit():
        start_number = int(last_copy.inventory_number) + 1
    else:
        start_number = 1  # Agar nusxalar yo'q bo'lsa, 1-dan boshlash

    # Yangi nusxalarni yaratish
    new_copies = [
        Copy(book=book, inventory_number=f"INV-{start_number + i}", is_available=True)
        for i in range(quantity)
    ]
    Copy.objects.bulk_create(new_copies)

def is_book_borrowed_by_student(student, book):
    """
    Talaba tomonidan kitobning ijaraga olinganligini tekshiradi.
    :param student: StudentProfile obyekti
    :param book: Book obyekti
    :return: True agar ijaraga olingan bo'lsa, aks holda False
    """
    return Rental.objects.filter(
        student=student,
        copy__book=book,
        return_date__isnull=True
    ).exists()