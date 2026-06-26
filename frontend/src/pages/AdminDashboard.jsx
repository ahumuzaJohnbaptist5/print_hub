import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate } from 'react-router-dom';
import { getApiUrl } from '../utils/api';

export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState('orders');
  const [orders, setOrders] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      setError('');
      const headers = { Authorization: `Token ${token}` };
      
      try {
        const [ordersRes, usersRes] = await Promise.all([
          axios.get(getApiUrl('orders/admin/'), { headers }),
          axios.get(getApiUrl('auth/users/'), { headers })
        ]);
        setOrders(ordersRes.data);
        setUsers(usersRes.data);
      } catch (err) {
        console.error(err);
        setError('Failed to load dashboard data. Make sure backend is running and you are logged in as admin.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const updateStatus = async (id, newStatus) => {
  if (!window.confirm(`Are you sure you want to mark this order as "${newStatus}"?`)) {
    return;
  }

  try {
    console.log(`Updating order ${id} to status: ${newStatus}`);
    
    const response = await axios.patch(
      getApiUrl(`orders/${id}/status/`),
      { status: newStatus }
    );
    
    console.log('✅ Update successful:', response.data);
    alert(`Order #${id} status updated to: ${response.data.status}`);
    
    // Refresh the orders list
    const res = await axios.get(getApiUrl('orders/admin/'));
    setOrders(res.data);
    
  } catch (err) {
    console.error('❌ Update failed:', err);
    console.error('Response:', err.response?.data);
    alert('Failed to update status. Check console for details.');
  }
};

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-white text-xl animate-pulse">Loading Dashboard...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 p-4 sm:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl sm:text-4xl font-bold text-white">Admin Dashboard</h1>
            <p className="text-gray-400 mt-1">Manage users and track print orders</p>
          </div>
          <div className="flex gap-3">
            <Link to="/" className="px-4 py-2 bg-white/10 text-white rounded-xl hover:bg-white/20 transition border border-white/10">
              ← Back to Home
            </Link>
            <button onClick={handleLogout} className="px-4 py-2 bg-red-500/20 text-red-400 border border-red-500/30 rounded-xl hover:bg-red-500/30 transition">
              Logout
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-500/20 border border-red-500/50 text-red-300 px-4 py-3 rounded-xl mb-6">
            {error}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-4 mb-6 border-b border-white/10 pb-2">
          <button
            onClick={() => setActiveTab('orders')}
            className={`px-6 py-2 rounded-lg font-semibold transition ${
              activeTab === 'orders' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            Print Orders ({orders.length})
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={`px-6 py-2 rounded-lg font-semibold transition ${
              activeTab === 'users' ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20' : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            Registered Users ({users.length})
          </button>
        </div>

        {/* Content Area */}
        <div className="bg-white/5 border border-white/10 backdrop-blur-md rounded-2xl overflow-hidden shadow-xl">
          {activeTab === 'orders' ? (
            orders.length === 0 ? (
              <div className="p-16 text-center text-gray-400">
                <div className="text-6xl mb-4 opacity-50">📄</div>
                <p className="text-lg">No orders yet. Student requests will appear here automatically.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[800px]">
                  <thead className="bg-white/5">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">ID</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">File</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Pages</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Price</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {orders.map(order => (
                      <tr key={order.id} className="hover:bg-white/5 transition">
                        <td className="px-6 py-4 text-white font-mono">#{order.id}</td>
                        <td className="px-6 py-4 text-gray-300 truncate max-w-xs" title={order.file_name}>{order.file_name}</td>
                        <td className="px-6 py-4 text-gray-300">{order.page_count}</td>
                        <td className="px-6 py-4 text-green-400 font-semibold">UGX {order.total_price?.toLocaleString()}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                            order.status === 'paid' ? 'bg-green-500/20 text-green-400' :
                            order.status === 'printing' ? 'bg-blue-500/20 text-blue-400' :
                            order.status === 'ready' ? 'bg-purple-500/20 text-purple-400' :
                            order.status === 'collected' ? 'bg-gray-500/20 text-gray-400' :
                            'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            {order.status}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex gap-2">
                            {order.status === 'paid' && (
                              <button 
                                onClick={() => updateStatus(order.id, 'printing')}
                                className="px-3 py-1 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 transition font-semibold"
                              >
                                Start Printing
                              </button>
                            )}
                            {order.status === 'printing' && (
                              <button 
                                onClick={() => updateStatus(order.id, 'ready')}
                                className="px-3 py-1 bg-purple-600 text-white text-xs rounded-lg hover:bg-purple-700 transition font-semibold"
                              >
                                Mark Ready
                              </button>
                            )}
                            {order.status === 'ready' && (
                              <span className="text-gray-400 text-xs italic">Awaiting pickup</span>
                            )}
                            {order.status === 'collected' && (
                              <span className="text-gray-500 text-xs">Completed</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : (
            users.length === 0 ? (
              <div className="p-16 text-center text-gray-400">
                <div className="text-6xl mb-4 opacity-50">👥</div>
                <p className="text-lg">No users registered yet.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[800px]">
                  <thead className="bg-white/5">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">User</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Email</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Phone</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Role</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Joined</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {users.map(user => (
                      <tr key={user.id} className="hover:bg-white/5 transition">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shadow-lg">
                              {user.first_name?.[0] || user.username?.[0] || 'U'}
                            </div>
                            <span className="text-white font-medium">{user.first_name} {user.last_name}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-gray-300">{user.email}</td>
                        <td className="px-6 py-4 text-gray-300">{user.phone_number || '—'}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                            user.role === 'admin' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                            user.role === 'agent' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                            'bg-green-500/20 text-green-400 border border-green-500/30'
                          }`}>
                            {user.role}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-400 text-sm">
                          {new Date(user.date_joined).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}