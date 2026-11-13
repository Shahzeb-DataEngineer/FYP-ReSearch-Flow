import React, { useState, useEffect } from 'react';
import { FaGoogle, FaGithub, FaEye, FaEyeSlash } from 'react-icons/fa';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import researchLogo from '../assets/researchLogo.jpg'

const AuthPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { signIn, signUp, signInWithProvider, loading: authLoading } = useAuth();
  
  const [isLogin, setIsLogin] = useState(searchParams.get('mode') === 'login');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    fullName: ''
  });
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  // Update mode based on URL parameter
  useEffect(() => {
    const mode = searchParams.get('mode');
    setIsLogin(mode === 'login');
  }, [searchParams]);

  const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const validatePassword = (password) => {
    return password.length >= 8;
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!validateEmail(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (!validatePassword(formData.password)) {
      newErrors.password = 'Password must be at least 8 characters long';
    }

    if (!isLogin) {
      if (!formData.fullName.trim()) {
        newErrors.fullName = 'Full name is required';
      }

      if (!formData.confirmPassword) {
        newErrors.confirmPassword = 'Please confirm your password';
      } else if (formData.password !== formData.confirmPassword) {
        newErrors.confirmPassword = 'Passwords do not match';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    setErrors({});
    setSuccessMessage('');

    try {
      if (isLogin) {
        // Handle sign in
        const { error } = await signIn(formData.email, formData.password);
        
        if (error) {
          setErrors({ submit: error });
        } else {
          navigate('/'); // Redirect to dashboard or home page
        }
      } else {
        // Handle sign up
        const { error } = await signUp(
          formData.email, 
          formData.password, 
          { full_name: formData.fullName }
        );
        
        if (error) {
          setErrors({ submit: error });
        } else {
          setSuccessMessage('Account created successfully! Please check your email to verify your account.');
          setFormData({ email: '', password: '', confirmPassword: '', fullName: '' });
        }
      }
    } catch {
      setErrors({ submit: 'An unexpected error occurred. Please try again.' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSocialLogin = async (provider) => {
    try {
      const { error } = await signInWithProvider(provider.toLowerCase());
      if (error) {
        setErrors({ submit: `Failed to sign in with ${provider}. Please try again.` });
      }
    } catch {
      setErrors({ submit: `Failed to sign in with ${provider}. Please try again.` });
    }
  };

  const toggleAuthMode = () => {
    setIsLogin(!isLogin);
    setFormData({ email: '', password: '', confirmPassword: '', fullName: '' });
    setErrors({});
    setSuccessMessage('');
    
    // Update URL
    const newMode = !isLogin ? 'login' : 'signup';
    navigate(`/auth?mode=${newMode}`, { replace: true });
  };

  return (
    <div className="min-h-screen bg-gray-50  viga-font flex items-center justify-center p-4">
      <div className="w-full my-10 max-w-md">
        {/* Logo and Title */}
        <div className="text-center justify-center gap-2 flex flex-row">
          <div>
            <img className='h-12 w-12 rounded-xl' src={researchLogo} />
          </div>
          <div className="text-black">
            <h1 className="text-lg font-semibold">ReSearch Flow</h1>
            <p className="text-sm text-gray-500">AI Research Assistant</p>
          </div>
        </div>

        {/* Main Form Card */}
        <div className="bg-white rounded-2xl p-8 mt-6 shadow-2xl border border-gray-200">
          <h2 className="text-2xl text-black text-center mb-2">
            {isLogin ? 'Login' : 'Create Account'}
          </h2>
          
          <p className="text-gray-500 text-xs text-center mb-6">
            By {isLogin ? 'signing in' : 'creating an account'} you agree to accept our{' '}
            <span className="text-black underline cursor-pointer hover:text-gray-600">Terms of Service</span> and{' '}
            <span className="text-black underline cursor-pointer hover:text-gray-600">Privacy Policy</span>
          </p>

          {/* Success Message */}
          {successMessage && (
            <div className="mb-4 p-3 bg-green-500/20 border border-green-500/30 rounded-lg">
              <p className="text-green-200 text-sm text-center">{successMessage}</p>
            </div>
          )}

          {/* Error Message */}
          {errors.submit && (
            <div className="mb-4 p-3 bg-red-100 border border-red-300 rounded-lg">
              <p className="text-red-700 text-sm text-center font-medium">{errors.submit}</p>
            </div>
          )}

          {/* Social Login Buttons */}
          <div className="flex justify-center space-x-6 mb-4">
            {/* Google */}
            <button
              onClick={() => handleSocialLogin("Google")}
              disabled={isLoading || authLoading}
              className="w-14 h-14 flex items-center justify-center rounded-full
                         bg-gray-100 hover:bg-gray-200 transition-all disabled:opacity-50 
                         border border-gray-300"
            >
              <FaGoogle className="text-red-500 text-2xl" />
            </button>

            {/* Github */}
            <button
              onClick={() => handleSocialLogin("Github")}
              disabled={isLoading || authLoading}
              className="w-14 h-14 flex items-center justify-center rounded-full
                         bg-gray-100 hover:bg-gray-200 transition-all disabled:opacity-50 
                         border border-gray-300"
            >
              <FaGithub className="text-black text-2xl" />
            </button>
          </div>

          <div className="relative mb-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-gray-500">Or continue with</span>
            </div>
          </div>

          {/* Form */}
          <div className="space-y-4">
            {/* Full Name Field (only for sign up) */}
            {!isLogin && (
              <div>
                <label className="block text-black text-sm font-medium mb-2">
                  Full Name
                </label>
                <input
                  type="text"
                  name="fullName"
                  value={formData.fullName}
                  onChange={handleInputChange}
                  placeholder="Enter your full name"
                  className={`w-full px-4 py-3 bg-gray-50 border rounded-lg text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-colors ${
                    errors.fullName ? 'border-red-500' : 'border-gray-300'
                  }`}
                />
                {errors.fullName && (
                  <p className="mt-1 text-red-500 text-sm">{errors.fullName}</p>
                )}
              </div>
            )}

            {/* Email Field */}
            <div>
              <label className="block text-black text-sm font-medium mb-2">
                Email
              </label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="Email"
                className={`w-full px-4 py-3 bg-gray-50 border rounded-lg text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-colors ${
                  errors.email ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.email && (
                <p className="mt-1 text-red-500 text-sm">{errors.email}</p>
              )}
            </div>

            {/* Password Field */}
            <div>
              <label className="block text-black text-sm font-medium mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="Password"
                  className={`w-full px-4 py-3 pr-12 bg-gray-50 border rounded-lg text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-colors ${
                    errors.password ? 'border-red-500' : 'border-gray-300'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-black transition-colors"
                >
                  {showPassword ? <FaEyeSlash /> : <FaEye />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-red-500 text-sm">{errors.password}</p>
              )}
            </div>

            {/* Confirm Password Field (only for sign up) */}
            {!isLogin && (
              <div>
                <label className="block text-black text-sm font-medium mb-2">
                  Re-Password*
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleInputChange}
                    placeholder="Re-Password"
                    className={`w-full px-4 py-3 pr-12 bg-gray-50 border rounded-lg text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-colors ${
                      errors.confirmPassword ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-black transition-colors"
                  >
                    {showConfirmPassword ? <FaEyeSlash /> : <FaEye />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="mt-1 text-red-500 text-sm">{errors.confirmPassword}</p>
                )}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isLoading || authLoading}
              className="w-full bg-black hover:bg-gray-800 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2"
            >
              {isLoading || authLoading ? (
                <div className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                  {isLogin ? 'Signing in...' : 'Creating account...'}
                </div>
              ) : (
                isLogin ? 'Sign in' : 'Sign up'
              )}
            </button>
          </div>

          {/* Toggle Auth Mode */}
          <div className="mt-6 text-center">
            <span className="text-gray-500 text-sm">
              {isLogin ? "Don't have an account?" : "Already have an account?"}{' '}
              <button
                onClick={toggleAuthMode}
                disabled={isLoading || authLoading}
                className="text-black font-semibold hover:underline focus:outline-none disabled:opacity-50"
              >
                {isLogin ? 'Sign up' : 'Log in'}
              </button>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthPage;