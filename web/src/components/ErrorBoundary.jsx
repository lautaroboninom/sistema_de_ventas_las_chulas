import React from "react";
export default class ErrorBoundary extends React.Component {
  constructor(p){ super(p); this.state={hasError:false,error:null}; }
  static getDerivedStateFromError(e){ return {hasError:true,error:e}; }
  componentDidCatch(e, info){ console.error("ErrorBoundary:", e, info); }
  render(){ return this.state.hasError
    ? <div style={{padding:16}}><h1>Ocurrió un error en la UI</h1>
        <pre style={{whiteSpace:"pre-wrap"}}>{String(this.state.error||"")}</pre></div>
    : this.props.children; }
}
