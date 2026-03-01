#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Verification Script for NCTB Books
Verifies completeness and accuracy of extracted book data
"""

import json
import collections

def load_json_data(filename='nctb_books.json'):
    """Load the JSON data file"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def verify_data_completeness(data):
    """Verify data completeness and generate reports"""
    books = data['books']
    metadata = data['metadata']
    
    print("=== NCTB Books Data Verification Report ===\n")
    
    # Overall statistics
    print(f"Total Books: {metadata['total_books']}")
    print(f"Years Covered: {', '.join(metadata['years'])}")
    print(f"Education Levels: {', '.join(metadata['education_levels'])}")
    print(f"Languages: {', '.join(metadata['languages'])}")
    print(f"Extraction Date: {metadata['extraction_date']}\n")
    
    # Books by year
    print("=== Books by Year ===")
    year_counts = collections.Counter(book['year'] for book in books)
    for year, count in year_counts.items():
        print(f"{year}: {count} books")
    print()
    
    # Books by education level
    print("=== Books by Education Level ===")
    level_counts = collections.Counter(book['education_level'] for book in books)
    for level, count in level_counts.items():
        print(f"{level}: {count} books")
    print()
    
    # Books by class
    print("=== Books by Class ===")
    class_counts = collections.Counter(book['class'] for book in books)
    for class_name, count in sorted(class_counts.items()):
        print(f"{class_name}: {count} books")
    print()
    
    # Books by subject
    print("=== Books by Subject ===")
    subject_counts = collections.Counter(book['subject'] for book in books)
    for subject, count in sorted(subject_counts.items()):
        print(f"{subject}: {count} books")
    print()
    
    # Books by language
    print("=== Books by Language ===")
    lang_counts = collections.Counter(book['language'] for book in books)
    for lang, count in lang_counts.items():
        print(f"{lang}: {count} books")
    print()
    
    # Download links analysis
    print("=== Download Links Analysis ===")
    total_links = 0
    link_types = collections.Counter()
    books_without_links = 0
    books_with_multiple_links = 0
    
    for book in books:
        links = book.get('download_links', [])
        if not links:
            books_without_links += 1
        else:
            total_links += len(links)
            if len(links) > 1:
                books_with_multiple_links += 1
            for link in links:
                link_types[link['type']] += 1
    
    print(f"Total Download Links: {total_links}")
    print(f"Average Links per Book: {total_links / len(books):.2f}")
    print(f"Books Without Download Links: {books_without_links}")
    print(f"Books With Multiple Download Links: {books_with_multiple_links}")
    print("Link Types:")
    for link_type, count in link_types.items():
        print(f"  {link_type}: {count} links")
    print()
    
    # Check for missing critical information
    print("=== Data Quality Checks ===")
    missing_serial = sum(1 for book in books if not book.get('serial'))
    missing_book_name = sum(1 for book in books if not book.get('book_name'))
    missing_subject = sum(1 for book in books if not book.get('subject'))
    missing_class = sum(1 for book in books if not book.get('class'))
    
    print(f"Books Missing Serial Number: {missing_serial}")
    print(f"Books Missing Book Name: {missing_book_name}")
    print(f"Books Missing Subject: {missing_subject}")
    print(f"Books Missing Class: {missing_class}")
    print()
    
    # Sample books from different categories
    print("=== Sample Books ===")
    print("Sample Primary Books:")
    primary_books = [book for book in books if book['education_level'] == 'প্রাথমিক'][:3]
    for book in primary_books:
        print(f"  - {book['book_name']} ({book['class']}, {book['subject']})")
    
    print("\nSample Secondary Books:")
    secondary_books = [book for book in books if book['education_level'] == 'মাধ্যমিক'][:3]
    for book in secondary_books:
        print(f"  - {book['book_name']} ({book['class']}, {book['subject']})")
    
    print("\nSample English Version Books:")
    english_books = [book for book in books if book['language'] == 'ইংরেজি'][:3]
    for book in english_books:
        print(f"  - {book['book_name']} ({book['class']}, {book['subject']})")
    print()
    
    # Check for duplicate entries
    print("=== Duplicate Check ===")
    book_identifiers = []
    duplicates = 0
    
    for book in books:
        identifier = f"{book['book_name']}_{book['class']}_{book['language']}_{book['year']}"
        if identifier in book_identifiers:
            duplicates += 1
        else:
            book_identifiers.append(identifier)
    
    print(f"Potential Duplicate Entries: {duplicates}")
    print()
    
    return {
        'total_books': len(books),
        'total_links': total_links,
        'books_without_links': books_without_links,
        'books_with_multiple_links': books_with_multiple_links,
        'missing_data': {
            'serial': missing_serial,
            'book_name': missing_book_name,
            'subject': missing_subject,
            'class': missing_class
        },
        'duplicates': duplicates
    }

def create_summary_report(data):
    """Create a detailed summary report"""
    books = data['books']
    
    # Create summary statistics
    summary = {
        'extraction_summary': {
            'total_books': len(books),
            'years': list(set(book['year'] for book in books)),
            'education_levels': list(set(book['education_level'] for book in books)),
            'classes': sorted(list(set(book['class'] for book in books))),
            'subjects': sorted(list(set(book['subject'] for book in books))),
            'languages': list(set(book['language'] for book in books))
        },
        'detailed_breakdown': {}
    }
    
    # Break down by year and education level
    for year in summary['extraction_summary']['years']:
        year_books = [book for book in books if book['year'] == year]
        summary['detailed_breakdown'][year] = {}
        
        for level in summary['extraction_summary']['education_levels']:
            level_books = [book for book in year_books if book['education_level'] == level]
            summary['detailed_breakdown'][year][level] = {
                'total_books': len(level_books),
                'classes': {},
                'subjects': {},
                'languages': {}
            }
            
            # Count by class
            class_counts = collections.Counter(book['class'] for book in level_books)
            summary['detailed_breakdown'][year][level]['classes'] = dict(class_counts)
            
            # Count by subject
            subject_counts = collections.Counter(book['subject'] for book in level_books)
            summary['detailed_breakdown'][year][level]['subjects'] = dict(subject_counts)
            
            # Count by language
            lang_counts = collections.Counter(book['language'] for book in level_books)
            summary['detailed_breakdown'][year][level]['languages'] = dict(lang_counts)
    
    return summary

def main():
    """Main verification function"""
    print("Loading data...")
    data = load_json_data()
    
    print("Verifying data completeness...")
    verification_results = verify_data_completeness(data)
    
    print("Creating summary report...")
    summary = create_summary_report(data)
    
    # Save summary report
    with open('verification_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("Verification complete! Summary saved to 'verification_summary.json'")
    
    # Final assessment
    print("\n=== Final Assessment ===")
    if verification_results['missing_data']['serial'] == 0 and \
       verification_results['missing_data']['book_name'] == 0 and \
       verification_results['missing_data']['subject'] == 0 and \
       verification_results['missing_data']['class'] == 0:
        print("✅ All critical data fields are complete!")
    else:
        print("⚠️  Some critical data fields are missing!")
    
    if verification_results['books_without_links'] == 0:
        print("✅ All books have download links!")
    else:
        print(f"⚠️  {verification_results['books_without_links']} books missing download links!")
    
    if verification_results['duplicates'] == 0:
        print("✅ No duplicate entries found!")
    else:
        print(f"⚠️  {verification_results['duplicates']} potential duplicate entries found!")

if __name__ == "__main__":
    main()
