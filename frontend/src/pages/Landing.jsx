import { Link } from 'react-router-dom';

export default function Landing() {
  return (
    <div className="min-h-screen bg-slate-900 text-white relative overflow-hidden">
      <div className="absolute top-0 left-0 w-96 h-96 bg-blue-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
      <div className="absolute top-0 right-0 w-96 h-96 bg-purple-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
      <div className="absolute -bottom-32 left-20 w-96 h-96 bg-pink-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>

      <main className="relative z-10 flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8 py-20 text-center">
        <div className="inline-flex items-center gap-2 bg-white/10 border border-white/20 backdrop-blur-sm px-4 py-1.5 rounded-full mb-8">
          <span className="text-sm font-medium text-gray-200">Live at Kabale University</span>
        </div>

        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tight mb-6 leading-tight">
          Print Smarter,{' '}
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400">
            Not Harder.
          </span>
        </h1>

        <p className="text-lg sm:text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
          Skip the queues. Upload your documents online, track your order, and pay in person at the pickup station after you approve your prints.
        </p>

        <div className="flex flex-wrap justify-center gap-4 mb-24">
          <Link
            to="/register"
            className="bg-gradient-to-r from-blue-600 to-purple-600 text-white font-bold px-8 py-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all hover:-translate-y-1"
          >
            Get Started
          </Link>
          <Link
            to="/login"
            className="bg-white/10 border border-white/20 text-white font-bold px-8 py-4 rounded-xl hover:bg-white/20 transition-all"
          >
            Login
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-5xl text-left">
          <div className="group p-8 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 hover:border-blue-500/30 transition-all duration-300 hover:-translate-y-2">
            <span className="inline-block text-xs font-bold uppercase tracking-wider text-blue-400 bg-blue-500/20 px-3 py-1 rounded-full mb-4">Step 1</span>
            <h3 className="text-xl font-bold text-white mb-3">Upload & Customize</h3>
            <p className="text-gray-400 leading-relaxed">Choose color, double-sided, and see your exact price before you submit. No payment required online.</p>
          </div>

          <div className="group p-8 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 hover:border-purple-500/30 transition-all duration-300 hover:-translate-y-2">
            <span className="inline-block text-xs font-bold uppercase tracking-wider text-purple-400 bg-purple-500/20 px-3 py-1 rounded-full mb-4">Step 2</span>
            <h3 className="text-xl font-bold text-white mb-3">We Print It</h3>
            <p className="text-gray-400 leading-relaxed">Your order goes to the campus station you picked. Track progress from your dashboard anytime.</p>
          </div>

          <div className="group p-8 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 hover:border-pink-500/30 transition-all duration-300 hover:-translate-y-2">
            <span className="inline-block text-xs font-bold uppercase tracking-wider text-pink-400 bg-pink-500/20 px-3 py-1 rounded-full mb-4">Step 3</span>
            <h3 className="text-xl font-bold text-white mb-3">Pay at Pickup</h3>
            <p className="text-gray-400 leading-relaxed">Review your prints at the station, pay in cash, and staff marks your order as paid. Main Campus, Engineering, or In Town.</p>
          </div>
        </div>
      </main>

      <footer className="relative z-10 border-t border-white/10 py-8 text-center text-gray-500 text-sm">
        <p>© 2026 PrintHub. Built for Kabale University Students.</p>
      </footer>

      <style>{`
        @keyframes blob {
          0% { transform: translate(0px, 0px) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
          100% { transform: translate(0px, 0px) scale(1); }
        }
        .animate-blob { animation: blob 7s infinite; }
        .animation-delay-2000 { animation-delay: 2s; }
        .animation-delay-4000 { animation-delay: 4s; }
      `}</style>
    </div>
  );
}
