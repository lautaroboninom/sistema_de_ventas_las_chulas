import React from "react";
const IS_DEV = import.meta.env.DEV;
export default class ErrorBoundary extends React.Component {
  constructor(p){ super(p); this.state={hasError:false,error:null}; }
  static getDerivedStateFromError(e){ return {hasError:true,error:e}; }
  componentDidCatch(e, info){ console.error("ErrorBoundary:", e, info); }
  render(){
    if (!this.state.hasError) return this.props.children;
    return (
      <div style={{padding:16}}>
        <h1>Ocurri un error en la UI</h1>
        {IS_DEV ? (
          <pre style={{whiteSpace:"pre-wrap"}}>{String(this.state.error || "")}</pre>
        ) : (
          <p>Intenta recargar la pgina o comuncate con soporte si el problema persiste.</p>
        )}
      </div>
    );
  }
}

