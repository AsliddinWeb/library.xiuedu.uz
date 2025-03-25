import requests
import random

from django.core.files import File
from io import BytesIO
import os

from django.http import JsonResponse
from django.shortcuts import render

from ..models import Book, Author, Genre
from user_app.utils import library_admin_role_required


@library_admin_role_required
def save_books(request):
    if request.method == "POST":
        url = request.POST.get("url")
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            books = data.get("results", [])

            for book in books:

                book_data = {
                    'title': book.get('title', '.'),
                    'author': book.get('author', {}).get('name', '.'),
                    'category': book.get('category', {}).get('title', 'Boshqa'),
                    'published_date': str(book.get('year')),  # Use the parse_date function
                    'description': book.get('description', '.'),
                    'electronic_version': book.get('source', '.'),
                    'page_count': random.randint(200, 400),
                    'cover_image': book.get('photo', ''),
                    'language': "O'zbekcha",
                    'isbn': "",
                }

                author, created = Author.objects.get_or_create(full_name=book_data['author'])
                category, created = Genre.objects.get_or_create(name=book_data['category'])

                # Create the book instance
                book_create = Book(
                    title=book_data['title'],
                    published_date=book_data['published_date'],
                    description=book_data['description'],
                    page_count=book_data['page_count'],
                    language=book_data['language'],
                    isbn=book_data['isbn'],
                    category=category,  # Assign the category directly here
                )

                # Save the book instance to generate a primary key (ID)
                book_create.save()

                # Now you can add the author to the many-to-many field
                book_create.authors.add(author)

                # Handle book cover image
                image_url = book_data['cover_image']
                if image_url:
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        img_temp = BytesIO(image_response.content)
                        book_create.cover_image.save(os.path.basename(image_url), File(img_temp))

                # Handle electronic version
                book_url = book_data['electronic_version']
                if book_url:
                    book_response = requests.get(book_url)
                    if book_response.status_code == 200:
                        book_temp = BytesIO(book_response.content)
                        book_create.electronic_version.save(os.path.basename(book_url), File(book_temp))

            return JsonResponse({
                "success": f"{len(books)} ta kitob muvaffaqqiyatli qo'shildi!"
            })


        else:
            return JsonResponse({"error": f"Xatolik yuz berdi: {response.status_code}"}, status=400)

    return render(request, 'custom/save_books.html')