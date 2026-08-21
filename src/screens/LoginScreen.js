import React,{useEffect,useState} from 'react';
import {Alert,KeyboardAvoidingView,Platform,Text,View,Linking} from 'react-native';
import {AppShell,Badge,Button,Card,Field} from '../components/UI';
import {api,BASE_URL} from '../services/api';
import {colors} from '../theme';

export default function LoginScreen({onLoggedIn}){
 const [mode,setMode]=useState('login');
 const [email,setEmail]=useState('');
 const [password,setPassword]=useState('');
 const [name,setName]=useState('');
 const [busy,setBusy]=useState(false);
 const [resetToken,setResetToken]=useState('');
 const [newPassword,setNewPassword]=useState('');
 useEffect(()=>{if(Platform.OS==='web'&&typeof window!=='undefined'){const token=new URLSearchParams(window.location.search).get('reset_token');if(token){setResetToken(token);setMode('reset')}}},[]);
 const submit=async()=>{try{setBusy(true);let d;if(mode==='login'){d=await api.login(email.trim(),password)}else if(mode==='register'){d=await api.register({name:name.trim(),email:email.trim(),password});}else if(mode==='forgot'){d=await api.forgotPassword(email.trim());Alert.alert('Password reset',d.message);setMode('login');return;}else{d=await api.resetPassword(resetToken,newPassword);Alert.alert('Password reset',d.message);setMode('login');return;}onLoggedIn(d.user)}catch(e){Alert.alert('Authentication',e.message)}finally{setBusy(false)}};
 const social=async provider=>{try{const redirect=Platform.OS==='web'?`${window.location.origin}/`: 'smartlearninglab://oauth';const url=`${BASE_URL}/auth/${provider}/start?redirect_uri=${encodeURIComponent(redirect)}`;if(Platform.OS==='web')window.location.href=url;else await Linking.openURL(url)}catch(e){Alert.alert('OAuth',e.message)}};
 const title=mode==='login'?'Welcome back':mode==='register'?'Create your student account':mode==='forgot'?'Reset your password':'Choose a new password';
 return <KeyboardAvoidingView style={{flex:1,backgroundColor:colors.background}} behavior={Platform.OS==='ios'?'padding':undefined}><AppShell><View style={{maxWidth:520,width:'100%',alignSelf:'center',marginTop:35}}><Badge tone="pink">FREE LEARNING PLATFORM</Badge><Text style={{fontSize:38,fontWeight:'900',color:colors.navy,marginTop:10}}>Smart Learning Lab</Text><Text style={{fontSize:16,color:colors.muted,marginTop:7,marginBottom:22}}>Learn courses, practice with tests, build streaks and grow your skills.</Text><Card><Text style={{fontSize:22,fontWeight:'900',color:colors.navy,marginBottom:18}}>{title}</Text>
 {mode==='register'&&<Field label="Full name" value={name} onChangeText={setName} placeholder="Your name"/>}
 {mode!=='reset'&&<Field label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" placeholder="you@example.com"/>}
 {mode==='reset'&&<><Field label="Reset token" value={resetToken} onChangeText={setResetToken} placeholder="Paste the token from your email"/><Field label="New password" value={newPassword} onChangeText={setNewPassword} secureTextEntry/></>}
 {(mode==='login'||mode==='register')&&<Field label="Password" value={password} onChangeText={setPassword} secureTextEntry placeholder="At least 8 characters"/>}
 <Button title={busy?'Please wait…':mode==='login'?'Sign in':mode==='register'?'Create account':mode==='forgot'?'Send reset email':'Reset password'} onPress={submit} disabled={busy|| (mode==='register' && (!name||password.length<8))}/>
 {mode==='login'&&<View style={{marginTop:14,gap:8}}><Button title="Create a new student account" variant="secondary" onPress={()=>setMode('register')}/><Button title="Forgot password?" variant="secondary" onPress={()=>setMode('forgot')}/><View style={{flexDirection:'row',gap:8,marginTop:4}}><View style={{flex:1}}><Button title="Continue with Google" variant="secondary" onPress={()=>social('google')}/></View><View style={{flex:1}}><Button title="Continue with GitHub" variant="secondary" onPress={()=>social('github')}/></View></View></View>}
 {mode!=='login'&&<Button title="Back to sign in" variant="secondary" onPress={()=>setMode('login')} style={{marginTop:10}}/>}
 {mode==='login'&&<Text style={{fontSize:12,color:colors.muted,marginTop:14}}>Root admin: admin@smartlearninglab.com / ChangeMe123!</Text>}
 </Card></View></AppShell></KeyboardAvoidingView>;
}
