import { useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { getApiUrl } from '../utils/api';
export default function OrderTracking() {
  const [orderId, setOrderId] = useState('');
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleTrack = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setOrder(null);

    try {
      // Fetch orders (In a real app, you'd have a specific endpoint for this)
      const res = await axios.get(getApiUrl('orders/admin/'));
      const found = res.data.find(o => o.id === parseInt(orderId));
      
      if (found) {
        setOrder(found);
      } else {
        setError('Order not found. Please check the ID and try again.');
      }
    } catch (err) {
      console.error(err);
      setError('Failed to connect to server. Make sure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  // Define the lifecycle steps
  const steps = ['paid', 'printing', 'ready', 'collected'];
  const currentStepIndex = order ? steps.indexOf(order.status) : -1;

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Blobs */}
      <div className="absolute top-0 left-0 w-96 h-96 bg-blue-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-purple-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>

      <div className="relative z-10 w-full max-w-3xl bg-white/5 border border-white/10 backdrop-blur-md rounded-3xl p-8 shadow-2xl">
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-3xl font-bold text-white">Track Your Order</h2>
          <Link to="/" className="text-blue-400 hover:text-blue-300 font-semibold">← Back Home</Link>
        </div>

        {/* Search Form */}
        <form onSubmit={handleTrack} className="flex gap-4 mb-10">
          <input 
            type="number" 
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            placeholder="Enter Order ID (e.g., 1, 2, 3)"
            className="flex-1 bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <button 
            type="submit" 
            disabled={loading}
            className="bg-blue-600 text-white px-8 py-3 rounded-xl font-semibold hover:bg-blue-700 transition disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Track'}
          </button>
        </form>

        {error && (
          <div className="bg-red-500/20 border border-red-500/50 text-red-300 px-4 py-3 rounded-xl mb-6 text-center">
            {error}
          </div>
        )}

        {/* Order Details & Progress Bar */}
        {order && (
          <div className="space-y-10 animate-fade-in">
            
            {/* Order Info Card */}
            <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <p className="text-gray-400 text-sm">Order ID</p>
                  <p className="text-2xl font-bold text-white">#{order.id}</p>
                </div>
                <div className="text-right">
                  <p className="text-gray-400 text-sm">Total Paid</p>
                  <p className="text-2xl font-bold text-green-400">UGX {order.total_price.toLocaleString()}</p>
                </div>
              </div>
              <div className="border-t border-white/10 pt-4 flex justify-between">
                <div>
                  <p className="text-gray-400 text-sm">File</p>
                  <p className="text-white font-medium truncate max-w-[200px]">{order.file_name}</p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Pages</p>
                  <p className="text-white font-medium">{order.page_count}</p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Station</p>
                  <p className="text-white font-medium">Main Campus</p>
                </div>
              </div>
            </div>

            {/* The Stepper Progress Bar */}
            <div className="relative">
              {/* Connecting Line Background */}
              <div className="absolute top-5 left-0 w-full h-1 bg-gray-700 -z-10"></div>
              {/* Connecting Line Progress */}
              <div 
                className="absolute top-5 left-0 h-1 bg-gradient-to-r from-blue-500 to-purple-500 -z-10 transition-all duration-1000"
                style={{ width: `${(currentStepIndex / (steps.length - 1)) * 100}%` }}
              ></div>

              {/* Steps */}
              <div className="flex justify-between">
                {steps.map((step, index) => {
                  const isCompleted = index <= currentStepIndex;
                  const isCurrent = index === currentStepIndex;
                  
                  return (
                    <div key={step} className="flex flex-col items-center relative">
                      {/* Circle */}
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-500 border-4 ${
                        isCompleted 
                          ? 'bg-blue-600 border-blue-400 text-white shadow-lg shadow-blue-500/50' 
                          : 'bg-slate-800 border-gray-600 text-gray-500'
                      }`}>
                        {isCompleted ? '✓' : index + 1}
                      </div>
                      {/* Label */}
                      <span className={`mt-3 text-xs font-semibold uppercase tracking-wider ${
                        isCurrent ? 'text-blue-400' : isCompleted ? 'text-white' : 'text-gray-500'
                      }`}>
                        {step}
                      </span>
                      {isCurrent && (
                        <span className="absolute -top-8 bg-blue-600 text-white text-xs px-2 py-1 rounded shadow-lg animate-bounce">
                          Current
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Status Message */}
            <div className="text-center">
              <p className="text-gray-300">
                {order.status === 'collected' 
                  ? "✅ Order has been collected. Thank you for using PrintHub!" 
                  : `⏳ Your order is currently being ${order.status}. Please wait for the next update.`}
              </p>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}