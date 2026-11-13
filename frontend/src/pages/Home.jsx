import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, BookOpen, Users } from 'lucide-react';
import SearchBar from '../components/SearchBar';

const FeatureCard = ({ icon, title, description }) => {
  // Assigned to a const (not a destructured rename): ESLint's
  // no-unused-vars does not count JSX usage of a destructured
  // parameter rename, so `({ icon: Icon })` was wrongly flagged.
  const Icon = icon;
  return (
  <div className="group p-6 bg-gray-50 rounded-lg border border-gray-300 hover:border-black transition-all duration-300 hover:shadow-lg">
    <div className="flex items-center mb-4">
      <div className="p-3 bg-black rounded-lg mr-4 group-hover:scale-110 transition-transform duration-300">
        <Icon className="w-6 h-6 text-white" />
      </div>
      <h3 className="text-xl font-semibold text-black">{title}</h3>
    </div>
    <p className="text-gray-600 leading-relaxed">{description}</p>
  </div>
  );
};

export default function Home() {
  const navigate = useNavigate();

  const handleSearch = (topic) => {
    navigate(`/results?topic=${encodeURIComponent(topic)}`);
  };

  return (
    <div className="min-h-screen relative viga-font overflow-hidden bg-white">
      <div className="relative z-10 min-h-screen flex flex-col">
        <main className="flex-1 flex flex-col items-center justify-center px-6 text-center">
          <div className="my-8 mx-auto">
            <h1 className="text-3xl lg:text-4xl text-black my-6 leading-tight">
              Find, Summarize & Visualize Research Papers Instantly
            </h1>

            <p className="text-xl text-gray-600 mb-12 mx-auto leading-relaxed">
              Enter a topic to get scholarly articles, summaries, and citation networks – all in one place
            </p>

            <div className="mb-16 flex justify-center">
              <SearchBar onSearch={handleSearch} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20">
              <div className="text-center">
                <div className="text-3xl font-bold text-black mb-2">10M+</div>
                <div className="text-gray-600">Research Papers</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-black mb-2">500K+</div>
                <div className="text-gray-600">Active Researchers</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-black mb-2">99.9%</div>
                <div className="text-gray-600">Uptime</div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
              <FeatureCard
                icon={Search}
                title="Smart Search"
                description="AI-powered search across millions of research papers with semantic understanding and relevance ranking."
              />
              <FeatureCard
                icon={BookOpen}
                title="Auto Summarization"
                description="Get key insights and summaries of complex research papers in seconds using advanced NLP."
              />
              <FeatureCard
                icon={Users}
                title="Citation Networks"
                description="Visualize connections between papers, authors, and research topics with interactive graphs."
              />
            </div>
          </div>
        </main>

      </div>
    </div>
  );
}