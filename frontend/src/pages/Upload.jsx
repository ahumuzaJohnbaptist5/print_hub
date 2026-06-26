import { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import PaymentButton from '../components/PaymentButton';
import { getApiUrl } from '../utils/api';

export default function Upload() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [pageCount, setPageCount] = useState(1);
  const [isColor, setIsColor] = useState(false);
  const [isDoubleSided, setIsDoubleSided] = useState(false);
  const [station, setStation] = useState('main-campus');
  
  const [orderId, setOrderId] = useState(null);
  const [showPayment, setShowPayment] = useState(false);

  // 💰 PRICING LOGIC
  const BASE_PRICE_PER_PAGE = 200;
  const COLOR_SURCHARGE_PER_PAGE = 100;
  
  const pricePerPage = isColor ? (BASE_PRICE_PER_PAGE + COLOR_SURCHARGE_PER_PAGE) : BASE_PRICE_PER_PAGE;
  const totalPrice = pricePerPage * pageCount;

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setSelectedFile(file);
    // Reset payment state if file changes
    setShowPayment(false);
    setOrderId(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return alert("Please select a file!");

    const user = JSON.parse(localStorage.getItem('user'));
    const userId = user?.id || 1;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('file_name', selectedFile.name);
    formData.append('page_count', pageCount);
    formData.append('is_color', isColor);
    formData.append('is_double_sided', isDoubleSided);
    formData.append('station', 1);
    formData.append('client_id', userId);

    try {
      const response = await axios.post(getApiUrl('orders/create/'), formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
   });
      setOrderId(response.data.id);
      setShowPayment(true);
    } catch (error) {
      console.error(error);
      alert("Failed to create order. Check console.");
    }
  };

  const handlePaymentSuccess = async (transactionId) => {
    try {
      await axios.post(getApiUrl('orders/verify/'), {
        transaction_id: transactionId,
        order_id: orderId
      });
      alert("Payment Successful! Your order is now being printed.");
    } catch (error) {
      console.error(error);
      alert("Payment verification failed. Please contact support.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Blobs */}
      <div className="absolute top-0 left-0 w-96 h-96 bg-blue-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-purple-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>

      <div className="relative z-10 w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* LEFT SIDE: The Form */}
        <div className="bg-white/5 border border-white/10 backdrop-blur-md rounded-3xl p-8 shadow-2xl">
          <Link to="/" className="text-blue-400 hover:text-blue-300 mb-4 inline-block text-sm">← Back to Home</Link>
          <h2 className="text-2xl font-bold text-white mb-6">Upload Document</h2>
          
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* File Upload */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Select File (PDF/Word/Image)</label>
              <input 
                type="file" 
                accept=".pdf,.doc,.docx,.jpg,.png"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer bg-white/5 border border-white/10 rounded-xl"
                required 
              />
              {selectedFile && (
                <p className="text-xs text-green-400 mt-2">✅ {selectedFile.name} selected</p>
              )}
            </div>

            {/* Page Count */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Number of Pages</label>
              <input 
                type="number" 
                min="1"
                value={pageCount}
                onChange={(e) => setPageCount(parseInt(e.target.value) || 1)}
                className="block w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                required 
              />
              <p className="text-xs text-gray-500 mt-1">Enter the total pages to print</p>
            </div>

            {/* Options */}
            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center space-x-3 bg-white/5 p-3 rounded-xl border border-white/10 cursor-pointer hover:bg-white/10 transition">
                <input type="checkbox" checked={isColor} onChange={() => setIsColor(!isColor)} className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4" />
                <div>
                  <span className="text-sm text-white block">Color Print</span>
                  <span className="text-xs text-gray-400">+100 UGX/page</span>
                </div>
              </label>
              
              <label className="flex items-center space-x-3 bg-white/5 p-3 rounded-xl border border-white/10 cursor-pointer hover:bg-white/10 transition">
                <input type="checkbox" checked={isDoubleSided} onChange={() => setIsDoubleSided(!isDoubleSided)} className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4" />
                <div>
                  <span className="text-sm text-white block">Double Sided</span>
                  <span className="text-xs text-gray-400">Saves paper</span>
                </div>
              </label>
            </div>

            {/* Station */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Pickup Station</label>
              <select 
                value={station}
                onChange={(e) => setStation(e.target.value)}
                className="block w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="main-campus" className="bg-slate-800">Main Campus</option>
                <option value="engineering" className="bg-slate-800">Engineering Faculty</option>
                <option value="in-town" className="bg-slate-800">In Town</option>
              </select>
            </div>
          </form>
        </div>

        {/* RIGHT SIDE: The Receipt / Price Breakdown */}
        <div className="bg-white/5 border border-white/10 backdrop-blur-md rounded-3xl p-8 shadow-2xl flex flex-col justify-between">
          <div>
            <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              🧾 Order Summary
            </h3>
            
            <div className="space-y-4 text-gray-300">
              <div className="flex justify-between items-center pb-3 border-b border-white/10">
                <span className="text-sm">Base Rate</span>
                <span className="font-mono">UGX {BASE_PRICE_PER_PAGE} / page</span>
              </div>
              
              <div className="flex justify-between items-center pb-3 border-b border-white/10">
                <span className="text-sm">Color Surcharge</span>
                <span className={`font-mono ${isColor ? 'text-yellow-400' : 'text-gray-500'}`}>
                  {isColor ? `+ UGX ${COLOR_SURCHARGE_PER_PAGE}` : 'None'}
                </span>
              </div>

              <div className="flex justify-between items-center pb-3 border-b border-white/10">
                <span className="text-sm">Effective Price Per Page</span>
                <span className="font-mono text-blue-400 font-bold">UGX {pricePerPage}</span>
              </div>

              <div className="flex justify-between items-center pb-3 border-b border-white/10">
                <span className="text-sm">Total Pages</span>
                <span className="font-mono">x {pageCount}</span>
              </div>
            </div>

            {/* Total Price Display */}
            <div className="mt-8 bg-gradient-to-r from-blue-600/20 to-purple-600/20 border border-blue-500/30 rounded-2xl p-6 text-center">
              <p className="text-gray-400 text-sm mb-1">Total Amount Due</p>
              <p className="text-4xl font-black text-white">UGX {totalPrice.toLocaleString()}</p>
            </div>
          </div>

          {/* Action Button */}
          <div className="mt-8">
            {showPayment ? (
              <PaymentButton 
                amount={totalPrice} 
                onPaymentSuccess={handlePaymentSuccess} 
              />
            ) : (
              <button 
                type="submit" 
                onClick={handleSubmit}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white font-bold py-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all duration-300 hover:-translate-y-1 disabled:opacity-50"
                disabled={!selectedFile}
              >
                Proceed to Payment
              </button>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}