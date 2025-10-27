from flask import Flask, render_template, request, jsonify
from amazon_search import scrape_amazon_products
from playwright.sync_api import sync_playwright
import json
import os

app = Flask(__name__)

@app.route('/')
def index():
    """Main page with search bar"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Handle search requests"""
    try:
        search_term = request.form.get('search_term', '').strip()
        max_pages = int(request.form.get('max_pages', 1))
        
        if not search_term:
            return jsonify({'error': 'Please enter a search term'}), 400
        
        # Run the Amazon scraper
        with sync_playwright() as playwright:
            products = scrape_amazon_products(playwright, search_term, max_pages)
        
        if products:
            # Save results to JSON file
            filename = f"search_results_{search_term.replace(' ', '_')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=2, ensure_ascii=False)
            
            return jsonify({
                'success': True,
                'products': products,
                'count': len(products),
                'filename': filename
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No products found'
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/results/<filename>')
def view_results(filename):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                products = json.load(f)
            return render_template('results.html', products=products, filename=filename)
        else:
            return "File not found", 404
    except Exception as e:
        return f"Error loading results: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
