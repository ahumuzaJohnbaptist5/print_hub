import { useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { getApiUrl } from '../utils/api';

export default function AgentDashboard() {
  const [orderId, setOrderId] = useState('');
  const [order, setOrder] = useState(null);
  const [message, setMessage] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    setMessage('');
    setOrder(null);
    setLoading(true);

    try {
      // Fetch orders to find the specific one
      const res = await axios.get(getApiUrl('orders/admin/'));
      const found = res.data.find(o => o.id === parseInt(orderId));
      
      if (found) {
        setOrder(found);
      } else {
        setMessage('Order ID not found. Please check and try again.');
        setIsSuccess(false);
      }
    } catch {
      setMessage('Failed to connect to server. Make sure backend is running.');
      setIsSuccess(false);
    } finally {
      setLoading(false);
    }
  };

  const markCollected = async () => {
    if (!window.confirm(`Are you sure you want to mark Order #${order.id} as COLLECTED?`)) {
      return;
    }
    
    setLoading(true);
    try {
      // Update status to 'collected'
      await axios.patch(getApiUrl(`orders/${order.id}/status/`), { 
        status: 'collected' 
      });
      
      setMessage(`✅ Success! Order #${order.id} has been marked as Collected.`);
      setIsSuccess(true);
      setOrder(null); 
      setOrderId(''); 
    } catch{
      setMessage('Failed to update order status. Check console.');
      setIsSuccess(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Blobs */}
      <div className="absolute top-0 left-0 w-96 h-96 bg-blue-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-green-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>

      <div className="relative z-10 w-full max-w-md bg-white/5 border border-white/10 backdrop-blur-md rounded-3xl p-8 shadow-2xl">
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-2xl font-bold text-white">Agent Handoff</h2>
          <Link to="/" className="text-blue-400 hover:text-blue-300 text-sm font-semibold">← Back Home</Link>
        </div>
        
        <p className="text-gray-400 text-sm mb-6 text-center">Enter the Order ID to mark it as collected by the student.</p>

        {/* Search Form */}
        <form onSubmit={handleSearch} className="flex gap-3 mb-6">
          <input 
            type="number" 
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            placeholder="Order ID (e.g., 1)"
            className="flex-1 bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <button 
            type="submit" 
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700 transition disabled:opacity-50"
          >
            {loading ? '...' : 'Find'}
          </button>
        </form>

        {/* Messages */}
        {message && (
          <div className={`px-4 py-3 rounded-xl mb-6 text-center text-sm font-medium ${
            isSuccess ? 'bg-green-500/20 border border-green-500/50 text-green-300' : 'bg-red-500/20 border border-red-500/50 text-red-300'
          }`}>
            {message}
          </div>
        )}

        {/* Order Details & Action */}
        {order && (
          <div className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-white/10 pb-4">
              <span className="text-gray-400 text-sm">Order ID</span>
              <span className="text-white font-bold text-lg">#{order.id}</span>
            </div>
            
            <div className="flex justify-between items-center border-b border-white/10 pb-4">
              <span className="text-gray-400 text-sm">File</span>
              <span className="text-white font-medium truncate max-w-[150px]">{order.file_name}</span>
            </div>

            <div className="flex justify-between items-center border-b border-white/10 pb-4">
              <span className="text-gray-400 text-sm">Pages</span>
              <span className="text-white font-medium">{order.page_count}</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Current Status</span>
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${
                order.status === 'ready' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' : 'bg-yellow-500/20 text-yellow-400'
              }`}>
                {order.status}
              </span>
            </div>

            {/* The Big Action Button */}
            <button 
              onClick={markCollected}
              disabled={loading || order.status === 'collected'}
              className={`w-full py-4 rounded-xl font-bold text-lg transition-all duration-300 shadow-lg ${
                order.status === 'collected' 
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed' 
                  : 'bg-gradient-to-r from-green-500 to-emerald-600 text-white hover:shadow-green-500/30 hover:-translate-y-1'
              }`}
            >
              {order.status === 'collected' ? 'Already Collected' : 'Mark as Collected'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}