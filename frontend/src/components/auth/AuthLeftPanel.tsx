import React from "react";

const AuthLeftPanel: React.FC = () => {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-indigo-700 dark:bg-indigo-950 p-12 text-white">
      <div className="flex flex-col h-[70%] items-center">
        {/* Branding */}
        <h1 className="font-sora text-3xl  font-bold tracking-tight text-white text-center">
          Enterprise Omni-Modal RAG Vault
        </h1>

        <p className="mt-2 text-sm font-medium text-indigo-200 text-center">
          Secure. Intelligent. Multi-Tenant.
        </p>

        {/* Illustration */}
        <img
          src="/man-sitting.png"
          alt=""
          className="mt-12 h-[67%] opacity-90"
        />

        {/* Trust Message */}
        <p className="text-sm mt-8 font-light tracking-wide text-indigo-300">
          Trusted by teams who value secure document intelligence.
        </p>
      </div>
    </div>
  );
};

export default AuthLeftPanel;
