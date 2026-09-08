// ---------------------------------------------------------------------
// Render product card
// ---------------------------------------------------------------------

function renderProductCard(product) {
    const stars = "★".repeat(Math.round(product.average_rating)) + "☆".repeat(5 - Math.round(product.average_rating));
    return `
        <div class="card product-card">
            <h3>${product.name}</h3>
            <p style="color:var(--text-muted); font-size:13px;">${product.description || ""}</p>
            <div class="rating-row">
                <span class="stars">${stars}</span>
                <span class="rating-text">${product.average_rating || "N/A"}</span>
                <span class="review-count">(${product.review_count} reviews)</span>
            </div>
            <p class="price">$${product.price.toFixed(2)}</p>
            <p class="stock">${product.stock > 0 ? product.stock + " in stock" : "Out of stock"}</p>
            <button class="btn" onclick="addToCart('${product.id}')">Add to Cart</button>
        </div>
    `;
}

function renderRecommendationSection(title, products, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    if (!products || products.length === 0) {
        container.innerHTML = `<div class="empty-rec">No products available.</div>`;
        return;
    }
    
    container.innerHTML = `
        <div class="recommendation-section">
            <h2>${title}</h2>
            <div class="grid">
                ${products.map(p => renderProductCard(p)).join("")}
            </div>
        </div>
    `;
}

// Load homepage recommendations
async function loadHomeRecommendations() {
    try {
        const data = await RecommendationsAPI.home(10);
        renderRecommendationSection("🔥 Trending Now", data.trending, "trendingSection");
        renderRecommendationSection("⭐ Top Rated", data.top_rated, "topRatedSection");
        renderRecommendationSection("✨ Featured Products", data.featured, "featuredSection");
    } catch (err) {
        console.error("Failed to load recommendations:", err);
    }
}

// Load user recommendations
async function loadUserRecommendations() {
    if (!Auth.isLoggedIn()) return;
    
    try {
        const data = await RecommendationsAPI.forMe(10);
        renderRecommendationSection("🎯 Recommended For You", data.recommendations, "recommendedSection");
        
        if (data.because_you_bought && data.because_you_bought.length > 0) {
            renderRecommendationSection("🛒 Because You Bought", data.because_you_bought, "becauseYouBoughtSection");
        }
    } catch (err) {
        console.error("Failed to load user recommendations:", err);
    }
}

// Load similar products
async function loadSimilarProducts(productId) {
    try {
        const similar = await RecommendationsAPI.similar(productId, 6);
        renderRecommendationSection("🔄 You May Also Like", similar, "similarProductsSection");
    } catch (err) {
        console.error("Failed to load similar products:", err);
    }
}

// Load trending products
async function loadTrendingProducts() {
    try {
        const trending = await RecommendationsAPI.trending(10);
        renderRecommendationSection("📈 Trending Products", trending, "trendingProductsSection");
    } catch (err) {
        console.error("Failed to load trending products:", err);
    }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("homePage")) {
        loadHomeRecommendations();
    }
    
    if (document.getElementById("recommendedSection") && Auth.isLoggedIn()) {
        loadUserRecommendations();
    }
    
    if (document.getElementById("trendingProductsSection")) {
        loadTrendingProducts();
    }
});