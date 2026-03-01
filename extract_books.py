#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Book Data Extractor for NCTB Textbooks
Extracts book information and download links from HTML files
"""

import os
import re
import json
import base64
from bs4 import BeautifulSoup
from urllib.parse import unquote
import html

class BookDataExtractor:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.all_books = []
        
    def decode_base64_content(self, encoded_content):
        """Decode base64 content from HTML"""
        try:
            decoded_bytes = base64.b64decode(encoded_content)
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            print(f"Error decoding base64: {e}")
            return ""
    
    def extract_books_from_html(self, file_path):
        """Extract book information from a single HTML file"""
        print(f"Processing: {os.path.basename(file_path)}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find the rt-renderer element with encoded content
            rt_renderer = soup.find('rt-renderer')
            if not rt_renderer:
                print(f"No rt-renderer found in {file_path}")
                return []
            
            encoded_content = rt_renderer.get('encoded-content', '')
            if not encoded_content:
                print(f"No encoded-content found in {file_path}")
                return []
            
            # Decode the content
            decoded_html = self.decode_base64_content(encoded_content)
            if not decoded_html:
                print(f"Failed to decode content from {file_path}")
                return []
            
            # Parse the decoded HTML
            decoded_soup = BeautifulSoup(decoded_html, 'html.parser')
            
            # Extract file information from filename
            filename = os.path.basename(file_path)
            year = filename.split(' ')[0]  # ২০২৫ or ২০২৬
            education_level = self.extract_education_level(filename)
            class_info = self.extract_class_info(filename)
            
            # Find all tables with book data
            tables = decoded_soup.find_all('table')
            books = []
            
            for table in tables:
                books.extend(self.extract_books_from_table(table, year, education_level, class_info))
            
            return books
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return []
    
    def extract_education_level(self, filename):
        """Extract education level from filename"""
        if 'প্রাথমিক' in filename:
            return 'প্রাথমিক'
        elif 'মাধ্যমিক' in filename:
            return 'মাধ্যমিক'
        elif 'উচ্চ মাধ্যমিক' in filename:
            return 'উচ্চ মাধ্যমিক'
        elif 'ইবতেদায়ি' in filename:
            return 'ইবতেদায়ি'
        elif 'কারিগরি' in filename:
            return 'কারিগরি'
        elif 'দাখিল' in filename:
            return 'দাখিল'
        elif 'ক্ষুদ্র নৃ-গোষ্ঠী' in filename:
            return 'ক্ষুদ্র নৃ-গোষ্ঠী'
        elif 'প্রাক-প্রাথমিক' in filename:
            return 'প্রাক-প্রাথমিক'
        else:
            return 'অন্যান্য'
    
    def extract_class_info(self, filename):
        """Extract class information from filename"""
        class_patterns = [
            (r'প্রথম শ্রেণি', '১ম শ্রেণি'),
            (r'দ্বিতীয় শ্রেণি', '২য় শ্রেণি'),
            (r'তৃতীয় শ্রেণি', '৩য় শ্রেণি'),
            (r'চতুর্থ শ্রেণি', '৪র্থ শ্রেণি'),
            (r'পঞ্চম শ্রেণি', '৫ম শ্রেণি'),
            (r'ষষ্ঠ শ্রেণি', '৬ষ্ঠ শ্রেণি'),
            (r'সপ্তম শ্রেণি', '৭ম শ্রেণি'),
            (r'অষ্টম শ্রেণি', '৮ম শ্রেণি'),
            (r'নবম-দশম শ্রেণি', '৯ম-১০ম শ্রেণি'),
            (r'নবম শ্রেণি', '৯ম শ্রেণি'),
            (r'দশম শ্রেণি', '১০ম শ্রেণি'),
            (r'একাদশ-দ্বাদশ শ্রেণি', '১১শ-১২শ শ্রেণি'),
            (r'একাদশ শ্রেণি', '১১শ শ্রেণি'),
            (r'দ্বাদশ শ্রেণি', '১২শ শ্রেণি'),
            (r'১০ম শ্রেণি', '১০ম শ্রেণি'),
            (r'৬ষ্ঠ শ্রেণি', '৬ষ্ঠ শ্রেণি'),
            (r'৭ম শ্রেণি', '৭ম শ্রেণি'),
            (r'৮ম শ্রেণি', '৮ম শ্রেণি'),
            (r'৯ম শ্রেণি', '৯ম শ্রেণি'),
        ]
        
        for pattern, class_name in class_patterns:
            if re.search(pattern, filename):
                return class_name
        
        return 'অন্যান্য শ্রেণি'
    
    def extract_books_from_table(self, table, year, education_level, class_info):
        """Extract books from a single table"""
        books = []
        rows = table.find_all('tr')
        
        if not rows:
            return books
        
        # Skip header row and extract data rows
        data_rows = rows[1:] if len(rows) > 1 else []
        
        for row in data_rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 5:  # Minimum expected columns
                continue
            
            try:
                # Extract book information from table cells
                serial = self.clean_text(cells[0].get_text()) if len(cells) > 0 else ""
                bangla_book_name = self.clean_text(cells[1].get_text()) if len(cells) > 1 else ""
                bangla_download = self.extract_download_links(cells[2]) if len(cells) > 2 else []
                english_book_name = self.clean_text(cells[3].get_text()) if len(cells) > 3 else ""
                english_download = self.extract_download_links(cells[4]) if len(cells) > 4 else []
                
                # Skip empty rows
                if not bangla_book_name and not english_book_name:
                    continue
                
                # Determine subject from book name
                subject = self.extract_subject(bangla_book_name or english_book_name)
                
                # Create book entries for Bangla version
                if bangla_book_name:
                    book = {
                        'serial': serial,
                        'book_name': bangla_book_name,
                        'language': 'বাংলা',
                        'version': 'বাংলা ভার্সন',
                        'subject': subject,
                        'class': class_info,
                        'education_level': education_level,
                        'year': year,
                        'download_links': bangla_download,
                        'file_source': os.path.join(self.base_dir, f"{year}/{education_level}")
                    }
                    books.append(book)
                
                # Create book entries for English version
                if english_book_name and english_book_name != bangla_book_name:
                    book = {
                        'serial': serial,
                        'book_name': english_book_name,
                        'language': 'ইংরেজি',
                        'version': 'ইংরেজি ভার্সন',
                        'subject': subject,
                        'class': class_info,
                        'education_level': education_level,
                        'year': year,
                        'download_links': english_download,
                        'file_source': os.path.join(self.base_dir, f"{year}/{education_level}")
                    }
                    books.append(book)
                    
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
        
        return books
    
    def extract_download_links(self, cell):
        """Extract download links from a table cell"""
        links = []
        
        if not cell:
            return links
        
        # Find all anchor tags
        anchors = cell.find_all('a')
        for anchor in anchors:
            href = anchor.get('href', '')
            title = anchor.get('title', '')
            text = self.clean_text(anchor.get_text())
            
            if href and not href.startswith('#'):
                link_info = {
                    'url': href,
                    'title': title or text,
                    'text': text,
                    'type': self.detect_link_type(href)
                }
                links.append(link_info)
        
        return links
    
    def detect_link_type(self, url):
        """Detect the type of download link"""
        url_lower = url.lower()
        if 'drive.google.com' in url_lower:
            return 'Google Drive'
        elif 'nctb.gov.bd' in url_lower:
            return 'NCTB Website'
        elif 'pdf' in url_lower:
            return 'Direct PDF'
        else:
            return 'Other'
    
    def extract_subject(self, book_name):
        """Extract subject from book name"""
        subject_patterns = [
            (r'বাংলা', 'বাংলা'),
            (r'ইংরেজি', 'ইংরেজি'),
            (r'গণিত', 'গণিত'),
            (r'বিজ্ঞান', 'বিজ্ঞান'),
            (r'সামাজিক বিজ্ঞান', 'সামাজিক বিজ্ঞান'),
            (r'ইতিহাস', 'ইতিহাস'),
            (r'ূগোল', 'ভূগোল'),
            (r'ধর্ম', 'ধর্ম'),
            (r'ইসলাম', 'ইসলাম শিক্ষা'),
            (r'হিন্দু', 'হিন্দু ধর্ম'),
            (r'বৌদ্ধ', 'বৌদ্ধ ধর্ম'),
            (r'খ্রিস্টান', 'খ্রিস্টান ধর্ম'),
            (r'কৃষি', 'কৃষি শিক্ষা'),
            (r'গার্হস্থ্য', 'গার্হস্থ্য বিজ্ঞান'),
            (r'আরবি', 'আরবি'),
            (r'ফারসি', 'ফারসি'),
            (r'কর্মজীবন', 'কর্মজীবন ও উপাভোক্তা শিক্ষা'),
            (r'স্বাস্থ্য', 'স্বাস্থ্য বিজ্ঞান'),
            (r'শারীরিক', 'শারীরিক শিক্ষা'),
            (r'চিত্র', 'চিত্রকলা'),
            (r'সঙ্গীত', 'সঙ্গীত'),
            (r'কম্পিউটার', 'কম্পিউটার শিক্ষা'),
            (r'বাংলাদেশ', 'বাংলাদেশ ও বিশ্বপরিচয়'),
            (r'পদার্থ', 'পদার্থবিজ্ঞান'),
            (r'রসায়ন', 'রসায়ন'),
            (r'ীববিজ্ঞান', 'জীববিজ্ঞান'),
            (r'উচ্চতর গণিত', 'উচ্চতর গণিত'),
            (r'অর্থনীতি', 'অর্থনীতি'),
            (r'রাষ্ট্রবিজ্ঞান', 'রাষ্ট্রবিজ্ঞান'),
            (r'হিসাববিজ্ঞান', 'হিসাববিজ্ঞান'),
            (r'ব্যবসায়', 'ব্যবসায় উদ্যোগ'),
            (r'পৌরনীতি', 'পৌরনীতি ও নাগরিকতা'),
        ]
        
        for pattern, subject in subject_patterns:
            if re.search(pattern, book_name, re.IGNORECASE):
                return subject
        
        return 'অন্যান্য বিষয়'
    
    def clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove extra whitespace and newlines
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common artifacts
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\xa0', ' ', text)
        
        return text
    
    def process_all_files(self):
        """Process all HTML files in the directory"""
        print("Starting book data extraction...")
        
        # Process 2025 files
        year_2025_dir = os.path.join(self.base_dir, '2025')
        if os.path.exists(year_2025_dir):
            for filename in os.listdir(year_2025_dir):
                if filename.endswith('.html'):
                    file_path = os.path.join(year_2025_dir, filename)
                    books = self.extract_books_from_html(file_path)
                    self.all_books.extend(books)
        
        # Process 2026 files
        year_2026_dir = os.path.join(self.base_dir, '2026')
        if os.path.exists(year_2026_dir):
            for filename in os.listdir(year_2026_dir):
                if filename.endswith('.html'):
                    file_path = os.path.join(year_2026_dir, filename)
                    books = self.extract_books_from_html(file_path)
                    self.all_books.extend(books)
        
        print(f"Total books extracted: {len(self.all_books)}")
        return self.all_books
    
    def save_to_json(self, output_file='nctb_books.json'):
        """Save extracted data to JSON file"""
        # Create a structured JSON output
        json_data = {
            'metadata': {
                'total_books': len(self.all_books),
                'years': list(set(book['year'] for book in self.all_books)),
                'education_levels': list(set(book['education_level'] for book in self.all_books)),
                'classes': list(set(book['class'] for book in self.all_books)),
                'languages': list(set(book['language'] for book in self.all_books)),
                'extraction_date': '2025-03-01'
            },
            'books': self.all_books
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"Data saved to {output_file}")
        return output_file

def main():
    """Main function to run the extractor"""
    base_dir = r"c:\Users\GourobSaha\OneDrive - Gourob Saha\Downloads\Book-link"
    
    extractor = BookDataExtractor(base_dir)
    books = extractor.process_all_files()
    
    # Save to JSON
    output_file = extractor.save_to_json()
    
    # Print summary
    print("\n=== Extraction Summary ===")
    print(f"Total books extracted: {len(books)}")
    
    # Group by year
    years = {}
    for book in books:
        year = book['year']
        if year not in years:
            years[year] = []
        years[year].append(book)
    
    for year, year_books in years.items():
        print(f"{year}: {len(year_books)} books")
    
    # Group by education level
    levels = {}
    for book in books:
        level = book['education_level']
        if level not in levels:
            levels[level] = []
        levels[level].append(book)
    
    print("\nBy Education Level:")
    for level, level_books in levels.items():
        print(f"{level}: {len(level_books)} books")

if __name__ == "__main__":
    main()
