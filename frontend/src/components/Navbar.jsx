import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();
  
  // Check if user is logged in
  const token = localStorage.getItem('token');
  const user = JSON.parse(localStorage.getItem('user') || 'null');
  const userRole = user?.role; // Get the user's role

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/');
    setIsOpen(false);
  };

  // Dynamic navigation based on user role
  const navLinks = token ? [
    { name: 'Upload', path: '/upload' },
    { name: 'Track Order', path: '/track' },
    // Only show Admin link if user is admin
    ...(userRole === 'admin' ? [{ name: 'Admin', path: '/admin-dashboard' }] : []),
    // Only show Agent link if user is agent
    ...(userRole === 'agent' ? [{ name: 'Agent', path: '/agent' }] : []),
  ] : [
    { name: 'Track Order', path: '/track' },
    { name: 'Login', path: '/login' },
  ];

  return (
    <nav className="fixed top-0 w-full z-50 bg-slate-900/80 backdrop-blur-md border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-tr from-blue-500 to-purple-600 rounded-lg flex items-center justify-center font-bold text-white">P</div>
            <span className="text-xl font-bold text-white tracking-tight">PrintHub</span>
          </Link>

          {/* Desktop Menu */}
          <div className="hidden md:flex items-center space-x-8">
            {navLinks.map(link => (
              <Link 
                key={link.name} 
                to={link.path} 
                className="text-gray-300 hover:text-white text-sm font-medium transition"
              >
                {link.name}
              </Link>
            ))}
            
            {token ? (
              <button 
                onClick={handleLogout}
                className="bg-red-500/20 text-red-400 border border-red-500/30 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-red-500/30 transition"
              >
                Logout
              </button>
            ) : (
              <Link 
                to="/register" 
                className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:shadow-lg hover:shadow-blue-500/30 transition"
              >
                Get Started
              </Link>
            )}
          </div>

          {/* Mobile Hamburger Button */}
          <div className="md:hidden flex items-center">
            <button 
              onClick={() => setIsOpen(!isOpen)}
              className="text-gray-300 hover:text-white focus:outline-none text-sm font-semibold px-2 py-1"
            >
              {isOpen ? 'Close' : 'Menu'}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {isOpen && (
        <div className="md:hidden bg-slate-900/95 backdrop-blur-lg border-b border-white/10 absolute w-full">
          <div className="px-4 pt-2 pb-6 space-y-2">
            {navLinks.map(link => (
              <Link 
                key={link.name} 
                to={link.path} 
                onClick={() => setIsOpen(false)}
                className="block px-3 py-3 rounded-md text-base font-medium text-gray-300 hover:text-white hover:bg-white/5 transition"
              >
                {link.name}
              </Link>
            ))}
            
            <div className="pt-4 border-t border-white/10">
              {token ? (
                <button 
                  onClick={handleLogout}
                  className="w-full text-left px-3 py-3 rounded-md text-base font-medium text-red-400 hover:bg-red-500/10 transition"
                >
                  Logout
                </button>
              ) : (
                <Link 
                  to="/register" 
                  onClick={() => setIsOpen(false)}
                  className="block w-full text-center bg-gradient-to-r from-blue-600 to-purple-600 text-white px-3 py-3 rounded-lg font-bold"
                >
                  Get Started
                </Link>
              )}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}