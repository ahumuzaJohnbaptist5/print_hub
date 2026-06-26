import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { getApiUrl } from '../utils/api';

export default function Register() {
  const navigate = useNavigate();
    const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    password2: '',
    first_name: '',
    last_name: '',
    phone_number: '',
    role: 'student' // <-- Add this default value
  });
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

    const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.password2) {
      setError('Passwords do not match');
      return;
    }

    try {
      await axios.post(getApiUrl('auth/register/'), formData);
      alert('Registration successful! Please login.');
      navigate('/login');
    } catch (err) {
      console.error(err);
      
      // Extract specific error messages from Django
      const errorData = err.response?.data;
      let errorMsg = 'Registration failed';
      
      if (errorData) {
        const errors = [];
        if (errorData.email) errors.push(...errorData.email);
        if (errorData.phone_number) errors.push(...errorData.phone_number);
        if (errorData.username) errors.push(...errorData.username);
        if (errorData.password) errors.push(...errorData.password);
        
        if (errors.length > 0) {
          errorMsg = errors.join(' ');
        }
      }
      
      setError(errorMsg);
    }
  };
  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-96 h-96 bg-blue-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-purple-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>

      <div className="relative z-10 w-full max-w-md bg-white/5 border border-white/10 backdrop-blur-md rounded-3xl p-8 shadow-2xl">
        <div className="text-center mb-6">
          <Link to="/" className="inline-block mb-4">
            <div className="w-12 h-12 bg-gradient-to-tr from-blue-500 to-purple-600 rounded-xl flex items-center justify-center font-bold text-white text-xl mx-auto">P</div>
          </Link>
          <h2 className="text-3xl font-bold text-white">Create Account</h2>
          <p className="text-gray-400 mt-2">Join PrintHub today</p>
        </div>

        {error && (
          <div className="bg-red-500/20 border border-red-500/50 text-red-300 px-4 py-3 rounded-xl mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <input name="first_name" placeholder="First Name" onChange={handleChange} className="w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" required />
            <input name="last_name" placeholder="Last Name" onChange={handleChange} className="w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" required />
          </div>
          <input name="username" placeholder="Username" onChange={handleChange} className="w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" required />
          <input name="email" type="email" placeholder="Email" onChange={handleChange} className="w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" required />
          <input name="phone_number" placeholder="Phone Number" onChange={handleChange} className="w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Account Type</label>
            <select 
              name="role" 
              value={formData.role} 
              onChange={handleChange}
              className="w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="student" className="bg-slate-800">Student (Client)</option>
              <option value="admin" className="bg-slate-800">Administrator</option>
              <option value="agent" className="bg-slate-800">Station Agent</option>
            </select>
          </div>
          <input name="password" type="password" placeholder="Password" onChange={handleChange} className="w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" required />
          <input name="password2" type="password" placeholder="Confirm Password" onChange={handleChange} className="w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" required />

          <button type="submit" className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white font-bold py-3 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all duration-300 hover:-translate-y-1">
            Create Account
          </button>
        </form>

        <p className="text-center text-gray-400 text-sm mt-6">
          Already have an account? <Link to="/login" className="text-blue-400 hover:text-blue-300 font-semibold">Sign In</Link>
        </p>
      </div>
    </div>
  );
}