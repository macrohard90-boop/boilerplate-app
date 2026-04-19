import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-glass-border mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div>
            <Link
              href="/"
              className="font-serif text-xl font-bold gradient-text"
            >
              Boilerplate
            </Link>
            <p className="mt-3 text-sm text-text-muted">
              A modern e-commerce platform.
            </p>
          </div>

          {/* Shop */}
          <div>
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              Shop
            </h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/products"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  All Products
                </Link>
              </li>
              <li>
                <Link
                  href="/categories/electronics"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  Electronics
                </Link>
              </li>
              <li>
                <Link
                  href="/categories/clothing"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  Clothing
                </Link>
              </li>
            </ul>
          </div>

          {/* Account */}
          <div>
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              Account
            </h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/dashboard"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  Dashboard
                </Link>
              </li>
              <li>
                <Link
                  href="/dashboard/orders"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  Orders
                </Link>
              </li>
              <li>
                <Link
                  href="/dashboard/wishlists"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  Wishlists
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              Legal
            </h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/dashboard/privacy"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  Privacy & GDPR
                </Link>
              </li>
              <li>
                <Link
                  href="/about"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  About
                </Link>
              </li>
              <li>
                <Link
                  href="/contact"
                  className="text-sm text-text-muted hover:text-text-secondary transition-colors"
                >
                  Contact
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-glass-border flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-xs text-text-muted">
            &copy; {new Date().getFullYear()} Boilerplate App. All rights
            reserved.
          </p>
          <p className="text-xs text-text-muted">Powered by Boilerplate</p>
        </div>
      </div>
    </footer>
  );
}
