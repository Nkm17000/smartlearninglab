import React from 'react';
import { Text, View } from 'react-native';
import { Button } from './UI';
import { colors } from '../theme';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || 'Unexpected application error.' };
  }

  componentDidCatch(error, info) {
    console.error('Smart Learning Lab UI error:', error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <View style={{ flex: 1, minHeight: '100vh', backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <View style={{ maxWidth: 560, width: '100%', backgroundColor: '#fff', borderRadius: 20, borderWidth: 1, borderColor: colors.border, padding: 28 }}>
          <Text style={{ fontSize: 28, fontWeight: '900', color: colors.navy }}>Something went wrong</Text>
          <Text style={{ color: colors.muted, lineHeight: 21, marginTop: 8 }}>
            The screen could not be rendered. Your data is safe. Try the screen again.
          </Text>
          <View style={{ backgroundColor: '#FEF2F2', borderRadius: 12, padding: 12, marginTop: 16 }}>
            <Text style={{ color: colors.danger, fontSize: 12 }}>{this.state.message}</Text>
          </View>
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 18 }}>
            <Button title="Reload screen" onPress={() => this.setState({ hasError: false, message: '' })} />
            <Button title="Reload app" variant="secondary" onPress={() => { if (typeof window !== 'undefined') window.location.reload(); }} />
          </View>
        </View>
      </View>
    );
  }
}
