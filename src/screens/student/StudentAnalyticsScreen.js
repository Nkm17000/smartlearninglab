import React, {useEffect, useState} from 'react';
import {Text, View} from 'react-native';
import {AppShell, Badge, Card, ErrorState, Header, Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function StudentAnalyticsScreen() {
  const [data, setData] = useState(null);
  const [advanced, setAdvanced] = useState(null);
  const [error, setError] = useState('');
  const load = async () => {
    try { setError(''); const [basic,adv] = await Promise.all([api.analytics(),api.advancedAnalytics()]); setData(basic); setAdvanced(adv); }
    catch (e) { setError(e.message); }
  };
  useEffect(() => { load(); }, []);
  if (error) return <AppShell><Header title="My Analytics"/><ErrorState title="Analytics could not load" message={error} onRetry={load}/></AppShell>;
  if (!data) return <AppShell><Loading label="Loading your analytics…"/></AppShell>;
  const stats = [
    ['Courses enrolled', data.courses_enrolled],
    ['Courses completed', data.courses_completed],
    ['Lessons completed', data.lessons_completed],
    ['Tests attempted', data.quiz_attempts],
    ['Tests passed', data.quizzes_passed],
    ['Average score', `${data.average_score}%`],
    ['Learning hours', data.learning_hours],
    ['XP', data.xp],
  ];
  return <AppShell>
    <Header eyebrow="Your learning" title="My Analytics" subtitle="See your learning activity, performance and streak."/>
    <View style={{flexDirection:'row',flexWrap:'wrap',gap:12}}>
      {stats.map(([label,value]) => <Card key={label} style={{flex:1,minWidth:180}}><Text style={{fontSize:12,color:colors.muted,fontWeight:'800'}}>{label}</Text><Text style={{fontSize:25,fontWeight:'900',color:colors.navy,marginTop:7}}>{value}</Text></Card>)}
    </View>
    {advanced && <Card><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>Advanced learning analytics</Text><View style={{flexDirection:'row',flexWrap:'wrap',gap:10,marginTop:12}}>{[['Courses',advanced.courses_enrolled],['Lessons',advanced.lessons_completed],['Tests',advanced.tests_taken],['Average',`${advanced.average_score}%`]].map(([l,v])=><View key={l} style={{padding:12,backgroundColor:'#F8FAFC',borderRadius:12,minWidth:110}}><Text style={{fontSize:11,color:colors.muted,fontWeight:'800'}}>{l}</Text><Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginTop:3}}>{v}</Text></View>)}</View></Card>}
    <Card style={{backgroundColor:colors.navy,borderColor:colors.navy}}>
      <Text style={{color:'#fff',fontSize:20,fontWeight:'900'}}>🔥 Learning streak</Text>
      <Text style={{color:'#CBD5E1',marginTop:7}}>Keep learning every day to grow your streak.</Text>
      <View style={{flexDirection:'row',gap:10,marginTop:18,flexWrap:'wrap'}}>
        <Badge tone="pink">Current: {data.streak?.current || 0} days</Badge>
        <Badge tone="orange">Best: {data.streak?.best || 0} days</Badge>
        {data.streak?.active_today && <Badge tone="green">Active today ✓</Badge>}
      </View>
    </Card>
    <Card>
      <Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>Level {data.level}</Text>
      <Text style={{color:colors.muted,marginTop:5}}>Earn XP by completing lessons, attempting tests and passing assessments.</Text>
      <View style={{height:10,backgroundColor:'#E5E7EB',borderRadius:10,marginTop:15,overflow:'hidden'}}>
        <View style={{height:10,width:`${Math.min(100,(data.xp % 500) / 5)}%`,backgroundColor:colors.primary}}/>
      </View>
      <Text style={{fontSize:12,color:colors.muted,marginTop:6}}>{data.xp % 500}/500 XP to next level</Text>
    </Card>
  </AppShell>;
}
