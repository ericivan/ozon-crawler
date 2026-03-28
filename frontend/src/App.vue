<template>
  <el-container style="min-height: 100vh">
    <el-aside width="220px" style="background: #1a1a2e">
      <div class="logo">
        <span class="logo-icon">🛒</span>
        <span class="logo-text">Ozon 选品</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#1a1a2e"
        text-color="#c0c4cc"
        active-text-color="#409eff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>选品总览</span>
        </el-menu-item>
        <el-menu-item index="/keywords">
          <el-icon><Collection /></el-icon>
          <span>关键词管理</span>
        </el-menu-item>
        <el-menu-item index="/kw-tool">
          <el-icon><MagicStick /></el-icon>
          <span>关键词工具</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="background: #fff; border-bottom: 1px solid #e4e7ed; line-height: 60px">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item>{{ $route.meta.title }}</el-breadcrumb-item>
        </el-breadcrumb>
      </el-header>
      <el-main style="background: #f5f7fa; padding: 24px">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.logo-icon { font-size: 24px; }
.logo-text { color: #fff; font-size: 16px; font-weight: 600; }
</style>
